from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score

from albus_hub.models.risk.clustering import evaluate_clusters
from albus_hub.models.risk.contracts import (
    ELIGIBILITY_COLUMN,
    LEAKAGE_COLUMNS,
    MODEL_FEATURES,
    TARGET_COLUMN,
    assert_no_leakage,
)
from albus_hub.models.risk.explainability import build_reference_values
from albus_hub.models.risk.features import build_risk_features
from albus_hub.models.risk.inference import RiskPredictor
from albus_hub.models.risk.metrics import classification_metrics, select_operating_threshold
from albus_hub.models.risk.model import ANN_CONFIGS, predict_ann, train_ann
from albus_hub.models.risk.plots import create_risk_figures
from albus_hub.models.risk.preprocessing import build_preprocessor, prepare_model_frame
from albus_hub.models.risk.probability import (
    apply_probability_calibrator,
    fit_probability_calibrator,
)


@dataclass(frozen=True)
class RiskTrainingConfig:
    """Parâmetros de execução e caminhos da frente de risco."""

    silver_path: Path
    risk_features_path: Path
    risk_scores_path: Path
    model_dir: Path
    metrics_path: Path
    figures_dir: Path
    model_version: str = "risk-ann-v1-20260820"
    train_fraction: float = 0.60
    validation_fraction: float = 0.20
    seed: int = 42


def _json_default(value):
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (np.integer, np.floating)):
        return value.item()
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    raise TypeError(f"Tipo não serializável: {type(value)!r}")


def _split_temporally(
    eligible: pd.DataFrame,
    config: RiskTrainingConfig,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    train_end = int(len(eligible) * config.train_fraction)
    validation_end = int(
        len(eligible) * (config.train_fraction + config.validation_fraction)
    )
    return (
        eligible.iloc[:train_end].copy(),
        eligible.iloc[train_end:validation_end].copy(),
        eligible.iloc[validation_end:].copy(),
    )


def _split_summary(frame: pd.DataFrame) -> dict[str, object]:
    return {
        "rows": len(frame),
        "positives": int(frame[TARGET_COLUMN].astype(bool).sum()),
        "positive_rate": float(frame[TARGET_COLUMN].astype(bool).mean()),
        "opened_at_min": frame["opened_at"].min(),
        "opened_at_max": frame["opened_at"].max(),
    }


def train_risk_model(config: RiskTrainingConfig) -> dict[str, object]:
    """Executa features, baseline, clusters, ANN, calibração, score e artefatos."""
    np.random.seed(config.seed)
    assert_no_leakage(MODEL_FEATURES)
    silver = pd.read_parquet(config.silver_path)
    risk_features = build_risk_features(silver)
    eligible = risk_features.loc[risk_features[ELIGIBILITY_COLUMN].eq(True)].copy()
    eligible[TARGET_COLUMN] = eligible[TARGET_COLUMN].astype(bool)
    eligible = eligible.sort_values(["opened_at", "incident_id"], kind="stable").reset_index(
        drop=True
    )
    train, validation, test = _split_temporally(eligible, config)

    risk_features["dataset_split"] = "not_eligible"
    split_by_id = {
        **{value: "train" for value in train["incident_id"]},
        **{value: "validation" for value in validation["incident_id"]},
        **{value: "test" for value in test["incident_id"]},
    }
    risk_features.loc[risk_features["incident_id"].isin(split_by_id), "dataset_split"] = (
        risk_features.loc[risk_features["incident_id"].isin(split_by_id), "incident_id"].map(
            split_by_id
        )
    )

    for path in [
        config.risk_features_path.parent,
        config.risk_scores_path.parent,
        config.model_dir,
        config.metrics_path.parent,
        config.figures_dir,
    ]:
        path.mkdir(parents=True, exist_ok=True)
    risk_features.to_parquet(config.risk_features_path, index=False)

    preprocessor = build_preprocessor()
    x_train = preprocessor.fit_transform(prepare_model_frame(train)).astype(np.float32)
    x_validation = preprocessor.transform(prepare_model_frame(validation)).astype(np.float32)
    x_test = preprocessor.transform(prepare_model_frame(test)).astype(np.float32)
    y_train = train[TARGET_COLUMN].astype(np.int8).to_numpy()
    y_validation = validation[TARGET_COLUMN].astype(np.int8).to_numpy()
    y_test = test[TARGET_COLUMN].astype(np.int8).to_numpy()

    baseline = LogisticRegression(
        class_weight="balanced",
        max_iter=1500,
        random_state=config.seed,
        solver="lbfgs",
    )
    baseline.fit(x_train, y_train)
    baseline_validation = baseline.predict_proba(x_validation)[:, 1]
    baseline_test = baseline.predict_proba(x_test)[:, 1]

    cluster_results = evaluate_clusters(
        x_train,
        y_train,
        x_validation,
        y_validation,
        float(average_precision_score(y_validation, baseline_validation)),
        config.seed,
    )
    ann_results = []
    trained_models = {}
    for index, ann_config in enumerate(ANN_CONFIGS):
        model, history, class_weight = train_ann(
            x_train,
            y_train,
            x_validation,
            y_validation,
            ann_config,
            seed=config.seed + index,
        )
        validation_probability = predict_ann(model, x_validation)
        test_probability = predict_ann(model, x_test)
        validation_pr_auc = average_precision_score(y_validation, validation_probability)
        ann_results.append(
            {
                "config": ann_config.to_dict(),
                "epochs_run": len(history["loss"]),
                "class_weight": class_weight,
                "validation_pr_auc": float(validation_pr_auc),
                "validation_metrics_at_0_5": classification_metrics(
                    y_validation, validation_probability, 0.5
                ),
                "history": {key: [float(value) for value in values] for key, values in history.items()},
            }
        )
        trained_models[ann_config.name] = (model, validation_probability, test_probability)

    selected_result = max(ann_results, key=lambda item: item["validation_pr_auc"])
    selected_name = selected_result["config"]["name"]
    selected_model, ann_validation_raw, ann_test_raw = trained_models[selected_name]
    calibrator = fit_probability_calibrator(ann_validation_raw, y_validation)
    ann_validation = apply_probability_calibrator(calibrator, ann_validation_raw)
    ann_test = apply_probability_calibrator(calibrator, ann_test_raw)
    threshold, threshold_table = select_operating_threshold(y_validation, ann_validation)

    baseline_metrics = {
        "validation": classification_metrics(y_validation, baseline_validation, 0.5),
        "test": classification_metrics(y_test, baseline_test, 0.5),
    }
    ann_metrics = {
        "validation": classification_metrics(y_validation, ann_validation, threshold),
        "test": classification_metrics(y_test, ann_test, threshold),
    }

    pressure_reference = float(
        max(train["assigned_group_incidents_previous_1d"].quantile(0.95), 1.0)
    )
    explanation_references = build_reference_values(train)
    metadata = {
        "model_version": config.model_version,
        "created_at_utc": datetime.now(UTC).isoformat(),
        "selected_ann_config": selected_result["config"],
        "transformed_dimension": int(x_train.shape[1]),
        "threshold": threshold,
        "minimum_recall_policy": 0.70,
        "pressure_reference_p95": pressure_reference,
        "explanation_reference_values": explanation_references,
        "model_features": MODEL_FEATURES,
        "leakage_columns": LEAKAGE_COLUMNS,
        "population_filter": f"{ELIGIBILITY_COLUMN} == True",
        "target_column": TARGET_COLUMN,
        "score_formula": (
            "round(100 * (0.70 * breach_probability + 0.20 * priority_impact "
            "+ 0.10 * operational_pressure))"
        ),
    }

    joblib.dump(preprocessor, config.model_dir / "preprocessor.joblib")
    joblib.dump(baseline, config.model_dir / "baseline_logistic.joblib")
    joblib.dump(calibrator, config.model_dir / "calibrator.joblib")
    selected_model.save_weights(config.model_dir / "ann.weights.h5")
    (config.model_dir / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2, default=_json_default),
        encoding="utf-8",
    )

    predictor = RiskPredictor(config.model_dir)
    risk_scores = predictor.predict_features(test.reset_index(drop=True))
    risk_scores.to_parquet(config.risk_scores_path, index=False)

    figures = create_risk_figures(
        eligible,
        y_test,
        baseline_test,
        ann_test,
        ann_metrics["test"],
        config.figures_dir,
    )
    metrics = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "config": asdict(config),
        "population": {
            "total_incidents": len(silver),
            "eligible_incidents": len(eligible),
            "positive_incidents": int(eligible[TARGET_COLUMN].sum()),
            "negative_incidents": int((~eligible[TARGET_COLUMN]).sum()),
            "positive_rate": float(eligible[TARGET_COLUMN].mean()),
        },
        "splits": {
            "train": _split_summary(train),
            "validation": _split_summary(validation),
            "test": _split_summary(test),
        },
        "preprocessing": {
            "input_features": MODEL_FEATURES,
            "transformed_dimension": int(x_train.shape[1]),
        },
        "baseline": baseline_metrics,
        "clustering": cluster_results,
        "ann_candidates": ann_results,
        "selected_ann": selected_name,
        "selected_threshold": threshold,
        "threshold_table": threshold_table.to_dict(orient="records"),
        "ann": ann_metrics,
        "risk_scores_rows": len(risk_scores),
        "figures": [str(path) for path in figures],
    }
    config.metrics_path.write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2, default=_json_default),
        encoding="utf-8",
    )
    return metrics
