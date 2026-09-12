from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

PRIORITY_SCOPES = ("ALL", "P2", "P3")

FEATURE_COLUMNS = [
    "trend",
    "lag_1",
    "lag_7",
    "rolling_7",
    "rolling_28",
    "dow_sin",
    "dow_cos",
]

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

    scoped["reference_date"] = pd.to_datetime(
        scoped["reference_date"],
        errors="raise",
    ).dt.normalize()

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


def build_training_features(
    scoped: pd.DataFrame,
) -> pd.DataFrame:
    result = scoped.copy()

    result["trend"] = np.arange(
        len(result),
        dtype=float,
    )

    result["lag_1"] = result["incident_count"].shift(1)

    result["lag_7"] = result["incident_count"].shift(7)

    shifted = result["incident_count"].shift(1)

    result["rolling_7"] = shifted.rolling(7).mean()

    result["rolling_28"] = shifted.rolling(28).mean()

    dow = result["reference_date"].dt.dayofweek

    result["dow_sin"] = np.sin(2 * np.pi * dow / 7)

    result["dow_cos"] = np.cos(2 * np.pi * dow / 7)

    return result.dropna().reset_index(drop=True)


def design_matrix(
    frame: pd.DataFrame,
) -> np.ndarray:
    features = frame[FEATURE_COLUMNS].to_numpy(dtype=float)

    return np.column_stack(
        [
            np.ones(len(frame)),
            features,
        ]
    )


def fit_model(
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


def evaluate_model(
    frame: pd.DataFrame,
) -> dict[str, float]:
    if len(frame) <= HOLDOUT_DAYS:
        raise ValueError("Histórico insuficiente para holdout.")

    train = frame.iloc[:-HOLDOUT_DAYS]

    test = frame.iloc[-HOLDOUT_DAYS:]

    coefficients = fit_model(train)

    prediction = design_matrix(test) @ coefficients

    prediction = np.clip(
        prediction,
        0,
        None,
    )

    actual = test["incident_count"].to_numpy(dtype=float)

    mae = np.mean(np.abs(actual - prediction))

    rmse = np.sqrt(np.mean((actual - prediction) ** 2))

    return {
        "mae": float(mae),
        "rmse": float(rmse),
    }


def build_prediction_vector(
    history: pd.Series,
    target_date: pd.Timestamp,
) -> np.ndarray:
    trend = float(len(history))

    dow = target_date.dayofweek

    return np.array(
        [
            1.0,
            trend,
            float(history.iloc[-1]),
            float(history.iloc[-7]),
            float(history.iloc[-7:].mean()),
            float(history.iloc[-28:].mean()),
            float(np.sin(2 * np.pi * dow / 7)),
            float(np.cos(2 * np.pi * dow / 7)),
        ]
    )


def forecast(
    scoped: pd.DataFrame,
    coefficients: np.ndarray,
) -> dict[int, tuple[pd.Timestamp, float]]:
    history = pd.Series(
        scoped["incident_count"].to_numpy(dtype=float),
        index=pd.DatetimeIndex(scoped["reference_date"]),
    )

    result = {}

    for step in range(1, 8):
        target_date = history.index.max() + pd.Timedelta(days=1)

        vector = build_prediction_vector(
            history,
            target_date,
        )

        value = float(vector @ coefficients)

        value = max(
            0.0,
            value,
        )

        history.loc[target_date] = value

        if step in {1, 7}:
            result[step] = (
                target_date,
                value,
            )

    return result


def save_model(
    model_path: Path,
    metadata_path: Path,
    coefficients: dict[str, np.ndarray],
    metadata: dict,
) -> None:
    model_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    np.savez(
        model_path,
        **coefficients,
    )

    metadata_path.write_text(
        json.dumps(
            metadata,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def load_model(
    model_path: Path,
) -> dict[str, np.ndarray]:
    if not model_path.exists():
        raise FileNotFoundError(f"Modelo não encontrado: {model_path}")

    loaded = np.load(model_path)

    return {scope: loaded[scope] for scope in PRIORITY_SCOPES}
