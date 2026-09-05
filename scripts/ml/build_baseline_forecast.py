from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from albus_hub.integration.volume_predictions import validate_volume_predictions

INPUT_PATH = Path("data/gold/daily_incident_volume.parquet")
OUTPUT_PATH = Path("data/gold/volume_predictions.parquet")

PRIORITY_SCOPES = ("ALL", "P2", "P3")
MODEL_VERSION = "linear-lag-baseline-v1"

HOLDOUT_DAYS = 60


def prepare_scope(
    frame: pd.DataFrame,
    priority_scope: str,
) -> pd.DataFrame:
    scoped = (
        frame.loc[
            frame["priority_scope"].eq(priority_scope),
            ["reference_date", "incident_count"],
        ]
        .copy()
        .sort_values("reference_date")
        .reset_index(drop=True)
    )

    if scoped.empty:
        raise ValueError(f"Nenhum dado encontrado para {priority_scope}.")

    if scoped["reference_date"].duplicated().any():
        raise ValueError(f"Existem datas duplicadas no escopo {priority_scope}.")

    expected_dates = pd.date_range(
        scoped["reference_date"].min(),
        scoped["reference_date"].max(),
        freq="D",
    )

    actual_dates = pd.DatetimeIndex(scoped["reference_date"])

    if not expected_dates.equals(actual_dates):
        raise ValueError(f"A série {priority_scope} não possui calendário diário contínuo.")

    scoped["incident_count"] = pd.to_numeric(
        scoped["incident_count"],
        errors="raise",
    ).astype(float)

    return scoped


def build_features(
    scoped: pd.DataFrame,
) -> pd.DataFrame:
    result = scoped.copy()

    result["trend"] = np.arange(len(result), dtype=float)

    result["lag_1"] = result["incident_count"].shift(1)
    result["lag_7"] = result["incident_count"].shift(7)

    shifted = result["incident_count"].shift(1)

    result["rolling_7"] = shifted.rolling(
        window=7,
        min_periods=7,
    ).mean()

    result["rolling_28"] = shifted.rolling(
        window=28,
        min_periods=28,
    ).mean()

    day_of_week = result["reference_date"].dt.dayofweek

    result["dow_sin"] = np.sin(2 * np.pi * day_of_week / 7)
    result["dow_cos"] = np.cos(2 * np.pi * day_of_week / 7)

    return result.dropna().reset_index(drop=True)


FEATURE_COLUMNS = [
    "trend",
    "lag_1",
    "lag_7",
    "rolling_7",
    "rolling_28",
    "dow_sin",
    "dow_cos",
]


def design_matrix(
    frame: pd.DataFrame,
) -> np.ndarray:
    features = frame[FEATURE_COLUMNS].to_numpy(dtype=float)

    intercept = np.ones(
        shape=(len(frame), 1),
        dtype=float,
    )

    return np.column_stack(
        [
            intercept,
            features,
        ]
    )


def fit_linear_regression(
    frame: pd.DataFrame,
) -> np.ndarray:
    x = design_matrix(frame)

    y = frame["incident_count"].to_numpy(dtype=float)

    coefficients, *_ = np.linalg.lstsq(
        x,
        y,
        rcond=None,
    )

    return coefficients


def evaluate_temporal_holdout(
    feature_frame: pd.DataFrame,
) -> tuple[float, float]:
    if len(feature_frame) <= HOLDOUT_DAYS:
        raise ValueError("Histórico insuficiente para avaliação temporal.")

    train = feature_frame.iloc[:-HOLDOUT_DAYS].copy()
    test = feature_frame.iloc[-HOLDOUT_DAYS:].copy()

    coefficients = fit_linear_regression(train)

    predictions = design_matrix(test) @ coefficients

    predictions = np.clip(
        predictions,
        a_min=0,
        a_max=None,
    )

    actual = test["incident_count"].to_numpy(dtype=float)

    mae = float(np.mean(np.abs(actual - predictions)))

    rmse = float(np.sqrt(np.mean((actual - predictions) ** 2)))

    return mae, rmse


def build_future_features(
    history: pd.Series,
    target_date: pd.Timestamp,
) -> np.ndarray:
    trend = float(len(history))

    lag_1 = float(history.iloc[-1])
    lag_7 = float(history.iloc[-7])

    rolling_7 = float(history.iloc[-7:].mean())

    rolling_28 = float(history.iloc[-28:].mean())

    day_of_week = target_date.dayofweek

    dow_sin = float(np.sin(2 * np.pi * day_of_week / 7))

    dow_cos = float(np.cos(2 * np.pi * day_of_week / 7))

    return np.array(
        [
            1.0,
            trend,
            lag_1,
            lag_7,
            rolling_7,
            rolling_28,
            dow_sin,
            dow_cos,
        ],
        dtype=float,
    )


def forecast_scope(
    scoped: pd.DataFrame,
    coefficients: np.ndarray,
) -> dict[int, tuple[pd.Timestamp, float]]:
    history = pd.Series(
        data=scoped["incident_count"].to_numpy(dtype=float),
        index=pd.DatetimeIndex(scoped["reference_date"]),
        dtype=float,
    )

    forecasts: dict[
        int,
        tuple[pd.Timestamp, float],
    ] = {}

    for step in range(1, 8):
        target_date = history.index.max() + pd.Timedelta(days=1)

        features = build_future_features(
            history,
            target_date,
        )

        prediction = float(features @ coefficients)

        prediction = max(
            0.0,
            prediction,
        )

        history.loc[target_date] = prediction

        if step in {1, 7}:
            forecasts[step] = (
                target_date,
                prediction,
            )

    return forecasts


def main() -> None:
    source = pd.read_parquet(INPUT_PATH)

    source["reference_date"] = pd.to_datetime(
        source["reference_date"],
        errors="raise",
    ).dt.normalize()

    generated_at = pd.Timestamp.now(tz="UTC").tz_localize(None)

    output_rows = []

    print("=== BASELINE DE PREVISAO DE VOLUME ===")
    print(f"Fonte: {INPUT_PATH}")
    print(f"Modelo: {MODEL_VERSION}")
    print()

    for priority_scope in PRIORITY_SCOPES:
        scoped = prepare_scope(
            source,
            priority_scope,
        )

        feature_frame = build_features(scoped)

        mae, rmse = evaluate_temporal_holdout(feature_frame)

        coefficients = fit_linear_regression(feature_frame)

        forecasts = forecast_scope(
            scoped,
            coefficients,
        )

        print(f"{priority_scope}: MAE={mae:.2f} | RMSE={rmse:.2f}")

        for step, horizon in (
            (1, "D+1"),
            (7, "D+7"),
        ):
            reference_date, prediction = forecasts[step]

            output_rows.append(
                {
                    "reference_date": reference_date,
                    "generated_at": generated_at,
                    "horizon": horizon,
                    "priority_scope": priority_scope,
                    "predicted_incident_count": round(
                        prediction,
                        2,
                    ),
                    "model_version": MODEL_VERSION,
                }
            )

            print(f"  {horizon}: {reference_date.date()} -> {prediction:.2f} incidentes")

        print()

    predictions = pd.DataFrame(output_rows)

    predictions = validate_volume_predictions(predictions)

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    predictions.to_parquet(
        OUTPUT_PATH,
        index=False,
    )

    print("=== ARTEFATO GERADO ===")
    print(OUTPUT_PATH)
    print()
    print(predictions.to_string(index=False))


if __name__ == "__main__":
    main()
