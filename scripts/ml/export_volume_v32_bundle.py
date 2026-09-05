from __future__ import annotations

import json
import runpy
from datetime import UTC, datetime
from pathlib import Path

import joblib
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import PoissonRegressor, Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[2]
PIPELINE = ROOT / "ml_volume" / "pipeline_prioridades.py"

OUTPUT_DIR = ROOT / "artifacts" / "runtime" / "ml_training_v32"
BUNDLE_PATH = OUTPUT_DIR / "model_bundle.joblib"
METADATA_PATH = OUTPUT_DIR / "metadata.json"


def fit_final_model(
    name,
    x_train,
    y_train,
    feats_level,
    feats_rate,
):
    if name in {"naive7", "media7", "ultimo"}:
        return None

    if y_train.nunique() <= 1:
        return {"constant": float(y_train.iloc[0]) if len(y_train) else 0.0}

    if name == "ridge":
        model = make_pipeline(
            StandardScaler(),
            Ridge(alpha=5.0),
        )
        model.fit(
            x_train[feats_level],
            y_train,
        )
        return model

    if name == "gbr":
        model = HistGradientBoostingRegressor(
            loss="poisson",
            max_depth=3,
            learning_rate=0.08,
            max_iter=250,
            min_samples_leaf=15,
            random_state=0,
        )
        model.fit(
            x_train[feats_level],
            y_train,
        )
        return model

    if name == "poisson_off":
        exposure = x_train["exp_roll7"].clip(lower=1e-6)

        rate = y_train / exposure

        if rate.sum() == 0:
            return {"constant": 0.0}

        model = make_pipeline(
            StandardScaler(),
            PoissonRegressor(
                alpha=1e-4,
                max_iter=6000,
            ),
        )

        model.fit(
            x_train[feats_rate],
            rate,
            poissonregressor__sample_weight=(exposure.values),
        )

        return model

    raise ValueError(f"Preditor desconhecido: {name}")


def predict_final_model(
    name,
    model,
    x_row,
    feats_level,
    feats_rate,
):
    if isinstance(model, dict):
        return max(
            0.0,
            float(model["constant"]),
        )

    if name == "poisson_off":
        exposure = max(
            1e-6,
            float(x_row["exp_roll7"].iloc[0]),
        )

        rate = float(model.predict(x_row[feats_rate])[0])

        return max(
            0.0,
            rate * exposure,
        )

    return max(
        0.0,
        float(model.predict(x_row[feats_level])[0]),
    )


def main():
    print("=== EXPORTACAO DO BUNDLE ML V3.2 ===")
    print("Executando metodologia canonica...")

    ns = runpy.run_path(
        str(PIPELINE),
        run_name="__main__",
    )

    model_version = ns["MODEL_VERSION"]
    last = ns["LAST"]
    series = ns["series"]
    chosen = ns["chosen"]
    metrics = ns["all_metrics"]
    pred_df = ns["pred_df"]

    build_xy = ns["build_Xy"]
    base_series = ns["base_series"]
    scale = ns["_s"]

    all_features = ns["ALLF"]
    feats_level = ns["FEATS_LEVEL"]
    feats_rate = ns["FEATS_RATE"]
    bases = set(ns["BASES"])

    components = {}

    print()
    print("Treinando componentes finais...")

    for scope, y in series.items():
        for horizon_days, horizon in [
            (1, "D+1"),
            (7, "D+7"),
        ]:
            predictor = chosen[(scope, horizon)]

            x, target = build_xy(
                y,
                horizon_days,
            )

            valid = x[all_features].notna().all(axis=1) & target.notna() & (target.index <= last)

            model = fit_final_model(
                predictor,
                x.loc[valid],
                target.loc[valid],
                feats_level,
                feats_rate,
            )

            coverage = metrics[scope][horizon]["_coverage"]

            q_low = float(coverage["q_low"])
            q_high = float(coverage["q_high"])

            future_date = last + ns["pd"].Timedelta(days=horizon_days)

            if predictor in bases:
                b = base_series(
                    y,
                    horizon_days,
                )
                prediction = max(
                    0.0,
                    float(b[predictor].loc[future_date]),
                )
            else:
                prediction = predict_final_model(
                    predictor,
                    model,
                    x.loc[[future_date]],
                    feats_level,
                    feats_rate,
                )

            lower = max(
                0.0,
                prediction + q_low * scale(prediction),
            )

            upper = max(
                lower,
                prediction + q_high * scale(prediction),
            )

            expected = pred_df[
                (pred_df["scope"] == scope)
                & (pred_df["horizon"] == horizon)
                & pred_df["actual_incidents"].isna()
            ].iloc[0]

            got = (
                int(round(prediction)),
                int(round(lower)),
                int(round(upper)),
            )

            wanted = (
                int(expected["predicted_incidents"]),
                int(expected["lower_bound"]),
                int(expected["upper_bound"]),
            )

            if got != wanted:
                raise RuntimeError(
                    f"Paridade falhou {scope} {horizon}: bundle={got} canonico={wanted}"
                )

            key = f"{scope}|{horizon}"

            components[key] = {
                "scope": scope,
                "horizon": horizon,
                "horizon_days": (horizon_days),
                "predictor": predictor,
                "model": model,
                "q_low": q_low,
                "q_high": q_high,
            }

            print(f"{scope:4} {horizon:3} {predictor:10} -> {got[0]} ({got[1]}-{got[2]}) [OK]")

    trained_at = datetime.now(UTC).isoformat()

    bundle = {
        "model_version": (model_version),
        "trained_at": trained_at,
        "training_end_date": (str(last.date())),
        "source": ("Silver governada data/silver/locaweb_incidents.parquet"),
        "methodology": ("v3.2 - deduplicacao + selecao honesta + intervalo conformal adaptativo"),
        "components": components,
    }

    metadata = {
        "model_version": (model_version),
        "trained_at": trained_at,
        "training_end_date": (str(last.date())),
        "component_count": (len(components)),
        "components": {
            key: {
                "scope": value["scope"],
                "horizon": (value["horizon"]),
                "predictor": (value["predictor"]),
                "q_low": (value["q_low"]),
                "q_high": (value["q_high"]),
            }
            for key, value in components.items()
        },
    }

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    joblib.dump(
        bundle,
        BUNDLE_PATH,
    )

    METADATA_PATH.write_text(
        json.dumps(
            metadata,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print()
    print(f"Bundle: {BUNDLE_PATH}")
    print(f"Metadata: {METADATA_PATH}")
    print(f"Componentes: {len(components)}")
    print("BUNDLE_PARITY=SUCCESS")


if __name__ == "__main__":
    main()
