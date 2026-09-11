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
from albus_hub.models.risk.metrics import (
    classification_metrics,
    lift_by_decile,
    ranking_metrics_at_k,
    select_operating_threshold,
)
from albus_hub.models.risk.model import (
    ANN_CONFIGS,
    predict_ann,
    train_ann,
)
from albus_hub.models.risk.plots import create_risk_figures
from albus_hub.models.risk.preprocessing import (
    build_preprocessor,
    prepare_model_frame,
)
from albus_hub.models.risk.probability import (
    apply_probability_calibrator,
    fit_probability_calibrator,
)

FINAL_VALIDATION_MONTHS = (
    "2025-04",
    "2025-05",
    "2025-06",
    "2025-07",
    "2025-08",
    "2025-09",
)

FINAL_TRAIN_END = pd.Period(
    "2025-09",
    freq="M",
)

FINAL_TEST_START = pd.Period(
    "2025-10",
    freq="M",
)

CHAMPION_C = 0.01


@dataclass(frozen=True)
class RiskTrainingConfig:
    """Parâmetros de execução e caminhos da frente de risco."""

    silver_path: Path
    risk_features_path: Path
    risk_scores_path: Path
    model_dir: Path
    metrics_path: Path
    figures_dir: Path
    model_version: str = "risk-logistic-v2-20260910"
    seed: int = 42


def _json_default(value):
    if isinstance(value, Path):
        return str(value)

    if isinstance(
        value,
        (
            np.integer,
            np.floating,
        ),
    ):
        return value.item()

    if isinstance(
        value,
        pd.Timestamp,
    ):
        return value.isoformat()

    raise TypeError(f"Tipo não serializável: {type(value)!r}")


def _split_summary(
    frame: pd.DataFrame,
) -> dict[str, object]:
    return {
        "rows": len(frame),
        "positives": int(frame[TARGET_COLUMN].astype(bool).sum()),
        "positive_rate": float(frame[TARGET_COLUMN].astype(bool).mean()),
        "opened_at_min": frame["opened_at"].min(),
        "opened_at_max": frame["opened_at"].max(),
    }


def _coerce_flag(
    series: pd.Series,
) -> pd.Series:
    """
    Normaliza flags booleanas usadas nas auditorias sem
    converter strings falsas em True.
    """

    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False).astype(bool)

    if pd.api.types.is_numeric_dtype(series):
        return (
            pd.to_numeric(
                series,
                errors="coerce",
            )
            .fillna(0)
            .ne(0)
        )

    normalized = series.astype("string").str.strip().str.lower()

    return normalized.isin(
        {
            "true",
            "1",
            "sim",
            "yes",
            "y",
        }
    )


def _build_label_audit(
    silver: pd.DataFrame,
) -> dict[str, object]:
    """Quantifica divergências entre fonte e regras recalculadas."""

    eligible = _coerce_flag(silver[ELIGIBILITY_COLUMN])

    positives = eligible & _coerce_flag(silver[TARGET_COLUMN])

    audit: dict[str, object] = {
        "eligibility_used": ELIGIBILITY_COLUMN,
        "target_used": TARGET_COLUMN,
        "eligible_rows": int(eligible.sum()),
        "positive_targets": int(positives.sum()),
    }

    for column in (
        "entered_kpi_rule_mismatch",
        "kpi_breached_rule_mismatch",
    ):
        if column not in silver.columns:
            audit[column] = {
                "column_present": False,
                "mismatches_total": None,
                "mismatches_eligible": None,
                "mismatches_among_positive_targets": None,
            }
            continue

        mismatch = _coerce_flag(silver[column])

        audit[column] = {
            "column_present": True,
            "mismatches_total": int(mismatch.sum()),
            "mismatch_rate_total": float(mismatch.mean()),
            "mismatches_eligible": int((mismatch & eligible).sum()),
            "mismatches_among_positive_targets": int((mismatch & positives).sum()),
        }

    return audit


def _probability_summary(
    probabilities: np.ndarray,
) -> dict[str, float]:
    """Resume probabilidades para diagnóstico de calibração."""

    values = np.asarray(
        probabilities,
        dtype=float,
    )

    return {
        "min": float(np.min(values)),
        "p05": float(
            np.quantile(
                values,
                0.05,
            )
        ),
        "p50": float(
            np.quantile(
                values,
                0.50,
            )
        ),
        "p95": float(
            np.quantile(
                values,
                0.95,
            )
        ),
        "max": float(np.max(values)),
        "mean": float(np.mean(values)),
    }


def _month_series(
    frame: pd.DataFrame,
) -> pd.Series:
    return pd.to_datetime(
        frame["opened_at"],
        errors="coerce",
    ).dt.to_period("M")


def _fit_logistic_model(
    train_frame: pd.DataFrame,
    *,
    seed: int,
):
    """
    Ajusta preprocessing e regressão logística champion.

    C=0.01 foi previamente selecionado por rolling temporal,
    usando critério maximin de PR-AUC.
    """

    preprocessor = build_preprocessor()

    x_train = preprocessor.fit_transform(prepare_model_frame(train_frame)).astype(np.float32)

    y_train = train_frame[TARGET_COLUMN].astype(np.int8).to_numpy()

    model = LogisticRegression(
        C=CHAMPION_C,
        class_weight="balanced",
        max_iter=1500,
        random_state=seed,
        solver="lbfgs",
    )

    model.fit(
        x_train,
        y_train,
    )

    return (
        preprocessor,
        model,
    )


def _build_logistic_oof(
    eligible: pd.DataFrame,
    *,
    seed: int,
) -> pd.DataFrame:
    """
    Gera previsões OOF temporais Abr–Set/2025.

    Para cada mês, o modelo usa apenas registros anteriores
    àquele mês.
    """

    months = _month_series(eligible)

    parts: list[pd.DataFrame] = []

    for month_str in FINAL_VALIDATION_MONTHS:
        month = pd.Period(
            month_str,
            freq="M",
        )

        train_fold = eligible.loc[months < month].copy()

        validation_fold = eligible.loc[months == month].copy()

        if train_fold.empty or validation_fold.empty:
            continue

        y_train = train_fold[TARGET_COLUMN].astype(np.int8).to_numpy()

        y_validation = validation_fold[TARGET_COLUMN].astype(np.int8).to_numpy()

        if np.unique(y_train).size < 2 or np.unique(y_validation).size < 2:
            continue

        preprocessor, model = _fit_logistic_model(
            train_fold,
            seed=seed,
        )

        x_validation = preprocessor.transform(prepare_model_frame(validation_fold)).astype(
            np.float32
        )

        raw_probability = model.predict_proba(x_validation)[:, 1]

        parts.append(
            pd.DataFrame(
                {
                    "incident_id": validation_fold["incident_id"].to_numpy(),
                    "month": month_str,
                    "target": y_validation,
                    "raw_probability": raw_probability,
                }
            )
        )

    if not parts:
        raise RuntimeError("Não foi possível gerar previsões OOF para calibração temporal.")

    return pd.concat(
        parts,
        ignore_index=True,
    )


def train_risk_model(
    config: RiskTrainingConfig,
) -> dict[str, object]:
    """
    Treina o champion de risco e preserva a ANN como challenger.

    Champion:
        regressão logística calibrada.

    Protocolo:
        - seleção de C por rolling temporal prévia;
        - OOF Abr–Set/2025 para Platt;
        - treino final até Set/2025;
        - teste final Out–Dez/2025.
    """

    np.random.seed(config.seed)

    assert_no_leakage(MODEL_FEATURES)

    silver = pd.read_parquet(config.silver_path)

    risk_features = build_risk_features(silver)

    eligible = risk_features.loc[risk_features[ELIGIBILITY_COLUMN].eq(True)].copy()

    eligible[TARGET_COLUMN] = eligible[TARGET_COLUMN].astype(bool)

    eligible = eligible.sort_values(
        [
            "opened_at",
            "incident_id",
        ],
        kind="stable",
    ).reset_index(drop=True)

    months = _month_series(eligible)

    final_train = eligible.loc[months <= FINAL_TRAIN_END].copy()

    final_test = eligible.loc[months >= FINAL_TEST_START].copy()

    if final_train.empty or final_test.empty:
        raise RuntimeError(
            "Protocolo temporal final requer treino até 2025-09 e teste a partir de 2025-10."
        )

    # ========================================================
    # Marcação do split no artefato de features
    # ========================================================

    risk_features["dataset_split"] = "not_eligible"

    train_ids = set(final_train["incident_id"])

    test_ids = set(final_test["incident_id"])

    risk_features.loc[
        risk_features["incident_id"].isin(train_ids),
        "dataset_split",
    ] = "pretest_train"

    risk_features.loc[
        risk_features["incident_id"].isin(test_ids),
        "dataset_split",
    ] = "final_test"

    # ========================================================
    # Diretórios
    # ========================================================

    for path in [
        config.risk_features_path.parent,
        config.risk_scores_path.parent,
        config.model_dir,
        config.metrics_path.parent,
        config.figures_dir,
    ]:
        path.mkdir(
            parents=True,
            exist_ok=True,
        )

    risk_features.to_parquet(
        config.risk_features_path,
        index=False,
    )

    # ========================================================
    # CHAMPION — OOF TEMPORAL
    # ========================================================

    logistic_oof = _build_logistic_oof(
        eligible,
        seed=config.seed,
    )

    oof_y = logistic_oof["target"].astype(np.int8).to_numpy()

    oof_raw = logistic_oof["raw_probability"].to_numpy(dtype=float)

    baseline_calibrator = fit_probability_calibrator(
        oof_raw,
        oof_y,
    )

    oof_calibrated = apply_probability_calibrator(
        baseline_calibrator,
        oof_raw,
    )

    logistic_oof["calibrated_probability"] = oof_calibrated

    (
        baseline_threshold,
        baseline_threshold_table,
    ) = select_operating_threshold(
        oof_y,
        oof_calibrated,
    )

    predictive_reference = np.sort(
        np.asarray(
            oof_calibrated,
            dtype=float,
        )
    )

    # ========================================================
    # CHAMPION — TREINO FINAL
    # ========================================================

    (
        preprocessor,
        baseline,
    ) = _fit_logistic_model(
        final_train,
        seed=config.seed,
    )

    x_final_test = preprocessor.transform(prepare_model_frame(final_test)).astype(np.float32)

    y_test = final_test[TARGET_COLUMN].astype(np.int8).to_numpy()

    baseline_test_raw = baseline.predict_proba(x_final_test)[:, 1]

    baseline_test = apply_probability_calibrator(
        baseline_calibrator,
        baseline_test_raw,
    )

    baseline_metrics = {
        "selected_config": {
            "C": CHAMPION_C,
            "class_weight": "balanced",
            "selection_method": "rolling temporal maximin PR-AUC",
        },
        "selected_threshold": baseline_threshold,
        "threshold_table": baseline_threshold_table.to_dict(orient="records"),
        "raw_validation_at_0_5": classification_metrics(
            oof_y,
            oof_raw,
            0.5,
        ),
        "raw_test_at_0_5": classification_metrics(
            y_test,
            baseline_test_raw,
            0.5,
        ),
        "validation": classification_metrics(
            oof_y,
            oof_calibrated,
            baseline_threshold,
        ),
        "test": classification_metrics(
            y_test,
            baseline_test,
            baseline_threshold,
        ),
        "probability_diagnostics": {
            "validation_raw": _probability_summary(oof_raw),
            "validation_calibrated": _probability_summary(oof_calibrated),
            "test_raw": _probability_summary(baseline_test_raw),
            "test_calibrated": _probability_summary(baseline_test),
            "oof_rows": int(len(logistic_oof)),
            "oof_positives": int(oof_y.sum()),
            "oof_positive_rate": float(oof_y.mean()),
        },
    }

    # ========================================================
    # ANN CHALLENGER
    # ========================================================

    challenger_split = int(len(final_train) * 0.75)

    ann_train = final_train.iloc[:challenger_split].copy()

    ann_validation = final_train.iloc[challenger_split:].copy()

    challenger_preprocessor = build_preprocessor()

    x_ann_train = challenger_preprocessor.fit_transform(prepare_model_frame(ann_train)).astype(
        np.float32
    )

    x_ann_validation = challenger_preprocessor.transform(
        prepare_model_frame(ann_validation)
    ).astype(np.float32)

    x_ann_test = challenger_preprocessor.transform(prepare_model_frame(final_test)).astype(
        np.float32
    )

    y_ann_train = ann_train[TARGET_COLUMN].astype(np.int8).to_numpy()

    y_ann_validation = ann_validation[TARGET_COLUMN].astype(np.int8).to_numpy()

    # Clustering permanece como análise exploratória.
    cluster_results = evaluate_clusters(
        x_ann_train,
        y_ann_train,
        x_ann_validation,
        y_ann_validation,
        float(
            average_precision_score(
                oof_y,
                oof_calibrated,
            )
        ),
        config.seed,
    )

    ann_results = []
    trained_models = {}

    for index, ann_config in enumerate(ANN_CONFIGS):
        (
            model,
            history,
            class_weight,
        ) = train_ann(
            x_ann_train,
            y_ann_train,
            x_ann_validation,
            y_ann_validation,
            ann_config,
            seed=(config.seed + index),
        )

        validation_probability = predict_ann(
            model,
            x_ann_validation,
        )

        test_probability = predict_ann(
            model,
            x_ann_test,
        )

        validation_pr_auc = average_precision_score(
            y_ann_validation,
            validation_probability,
        )

        ann_results.append(
            {
                "config": ann_config.to_dict(),
                "epochs_run": len(history["loss"]),
                "class_weight": class_weight,
                "validation_pr_auc": float(validation_pr_auc),
                "validation_metrics_at_0_5": classification_metrics(
                    y_ann_validation,
                    validation_probability,
                    0.5,
                ),
                "history": {
                    key: [float(value) for value in values] for key, values in history.items()
                },
            }
        )

        trained_models[ann_config.name] = (
            model,
            validation_probability,
            test_probability,
        )

    selected_result = max(
        ann_results,
        key=lambda item: item["validation_pr_auc"],
    )

    selected_name = selected_result["config"]["name"]

    (
        selected_model,
        ann_validation_raw,
        ann_test_raw,
    ) = trained_models[selected_name]

    ann_calibrator = fit_probability_calibrator(
        ann_validation_raw,
        y_ann_validation,
    )

    ann_validation_calibrated = apply_probability_calibrator(
        ann_calibrator,
        ann_validation_raw,
    )

    ann_test = apply_probability_calibrator(
        ann_calibrator,
        ann_test_raw,
    )

    (
        ann_threshold,
        ann_threshold_table,
    ) = select_operating_threshold(
        y_ann_validation,
        ann_validation_calibrated,
    )

    ann_metrics = {
        "validation": classification_metrics(
            y_ann_validation,
            ann_validation_calibrated,
            ann_threshold,
        ),
        "test": classification_metrics(
            y_test,
            ann_test,
            ann_threshold,
        ),
    }

    # ========================================================
    # METADADOS OPERACIONAIS
    # ========================================================

    pressure_reference = float(
        max(
            final_train["assigned_group_incidents_previous_1d"].quantile(0.95),
            1.0,
        )
    )

    explanation_references = build_reference_values(final_train)

    transformed_dimension = int(
        preprocessor.transform(prepare_model_frame(final_train.iloc[[0]])).shape[1]
    )

    metadata = {
        "model_version": config.model_version,
        "created_at_utc": datetime.now(UTC).isoformat(),
        "champion_model": "logistic_regression",
        "champion_reason": (
            "Melhor equilíbrio entre estabilidade temporal, "
            "priorização operacional, calibração e interpretabilidade."
        ),
        "champion_protocol": {
            "hyperparameter_selection": "rolling temporal Apr-Sep/2025; maximin PR-AUC",
            "selected_c": CHAMPION_C,
            "calibration": "Platt scaling sobre previsões OOF temporais Apr-Sep/2025",
            "final_train": "incidentes elegíveis até 2025-09",
            "final_test": "incidentes elegíveis a partir de 2025-10",
        },
        "transformed_dimension": transformed_dimension,
        "threshold": baseline_threshold,
        "minimum_recall_policy": 0.70,
        "baseline_selected_config": {
            "C": CHAMPION_C,
            "class_weight": "balanced",
        },
        "baseline_threshold": baseline_threshold,
        "selected_ann_config": selected_result["config"],
        "ann_threshold": ann_threshold,
        "pressure_reference_p95": pressure_reference,
        "explanation_reference_values": explanation_references,
        "model_features": MODEL_FEATURES,
        "leakage_columns": LEAKAGE_COLUMNS,
        "population_filter": f"{ELIGIBILITY_COLUMN} == True",
        "target_column": TARGET_COLUMN,
        "score_formula": (
            "round(100 * "
            "(0.80 * predictive_risk_index "
            "+ 0.15 * priority_impact "
            "+ 0.05 * operational_pressure))"
        ),
        "predictive_risk_index_definition": (
            "Percentil histórico da breach_probability calibrada "
            "em relação à distribuição OOF pré-teste."
        ),
        "risk_level_thresholds": {
            "baixo": "0-39",
            "moderado": "40-59",
            "alto": "60-79",
            "crítico": "80-100",
        },
    }

    # ========================================================
    # ARTEFATOS
    # ========================================================

    joblib.dump(
        preprocessor,
        config.model_dir / "preprocessor.joblib",
    )

    joblib.dump(
        baseline,
        config.model_dir / "baseline_logistic.joblib",
    )

    joblib.dump(
        baseline_calibrator,
        config.model_dir / "baseline_calibrator.joblib",
    )

    np.save(
        config.model_dir / "predictive_reference.npy",
        predictive_reference,
    )

    # Challenger ANN preservado para rastreabilidade acadêmica.
    joblib.dump(
        ann_calibrator,
        config.model_dir / "calibrator.joblib",
    )

    selected_model.save_weights(config.model_dir / "ann.weights.h5")

    (config.model_dir / "metadata.json").write_text(
        json.dumps(
            metadata,
            ensure_ascii=False,
            indent=2,
            default=_json_default,
        ),
        encoding="utf-8",
    )

    # ========================================================
    # RISK SCORE FINAL
    # ========================================================

    predictor = RiskPredictor(config.model_dir)

    risk_scores = predictor.predict_features(final_test.reset_index(drop=True))

    risk_scores.to_parquet(
        config.risk_scores_path,
        index=False,
    )

    # ========================================================
    # FIGURAS
    # ========================================================

    figures = create_risk_figures(
        eligible,
        y_test,
        baseline_test,
        ann_test,
        ann_metrics["test"],
        config.figures_dir,
    )

    # ========================================================
    # AUDITORIA / PRIORIZAÇÃO
    # ========================================================

    label_audit = _build_label_audit(silver)

    prioritization = {
        "champion_logistic": {
            "base_rate": float(np.mean(y_test)),
            "at_k": ranking_metrics_at_k(
                y_test,
                baseline_test,
            ),
            "lift_by_decile": lift_by_decile(
                y_test,
                baseline_test,
            ),
        },
        "ann_challenger": {
            "base_rate": float(np.mean(y_test)),
            "at_k": ranking_metrics_at_k(
                y_test,
                ann_test,
            ),
            "lift_by_decile": lift_by_decile(
                y_test,
                ann_test,
            ),
        },
    }

    # ========================================================
    # MÉTRICAS
    # ========================================================

    metrics = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "config": asdict(config),
        "label_audit": label_audit,
        "population": {
            "total_incidents": len(silver),
            "eligible_incidents": len(eligible),
            "positive_incidents": int(eligible[TARGET_COLUMN].sum()),
            "negative_incidents": int((~eligible[TARGET_COLUMN]).sum()),
            "positive_rate": float(eligible[TARGET_COLUMN].mean()),
        },
        "splits": {
            "champion_final_train": _split_summary(final_train),
            "champion_oof_validation": {
                "rows": int(len(logistic_oof)),
                "positives": int(oof_y.sum()),
                "positive_rate": float(oof_y.mean()),
                "months": list(FINAL_VALIDATION_MONTHS),
            },
            "champion_final_test": _split_summary(final_test),
            "ann_challenger_train": _split_summary(ann_train),
            "ann_challenger_validation": _split_summary(ann_validation),
        },
        "preprocessing": {
            "input_features": MODEL_FEATURES,
            "transformed_dimension": transformed_dimension,
        },
        "champion": {
            "model": "logistic_regression",
            "selected_config": {
                "C": CHAMPION_C,
                "class_weight": "balanced",
            },
            "metrics": baseline_metrics,
        },
        # Mantido por compatibilidade com consumidores existentes.
        "baseline": baseline_metrics,
        "prioritization": prioritization,
        "clustering": cluster_results,
        "ann_candidates": ann_results,
        "selected_ann": selected_name,
        "selected_threshold": baseline_threshold,
        "threshold_table": baseline_threshold_table.to_dict(orient="records"),
        "ann_threshold": ann_threshold,
        "ann_threshold_table": ann_threshold_table.to_dict(orient="records"),
        "ann": ann_metrics,
        "risk_scores_rows": len(risk_scores),
        "figures": [str(path) for path in figures],
    }

    config.metrics_path.write_text(
        json.dumps(
            metrics,
            ensure_ascii=False,
            indent=2,
            default=_json_default,
        ),
        encoding="utf-8",
    )

    return metrics
