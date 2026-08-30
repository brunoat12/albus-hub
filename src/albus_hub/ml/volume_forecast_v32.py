from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import holidays
import joblib
import numpy as np
import pandas as pd


MODEL_START_DATE = pd.Timestamp("2025-01-01")

SCOPES: dict[str, int | None] = {
    "ALL": None,
    "P1": 1,
    "P2": 2,
    "P3": 3,
    "P4": 4,
    "P5": 5,
}

HORIZONS = {
    "D+1": 1,
    "D+7": 7,
}

BASES = {
    "naive7",
    "media7",
    "ultimo",
}

CALENDAR_COLUMNS = [
    *[f"dow_{value}" for value in range(7)],
    "is_weekend",
    "is_holiday",
    "black_week",
    "dec_season",
]

FEATURES_LEVEL = [
    "seas_lag7",
    "seas_lag14",
    "last",
    "roll7_mean",
    "roll7_std",
    "roll28_mean",
    "exp_last",
    "exp_roll7",
    "trend",
    *CALENDAR_COLUMNS,
]

FEATURES_RATE = [
    "r_last",
    "r_roll7",
    "r_seas7",
    *CALENDAR_COLUMNS,
]

ALL_FEATURES = list(
    dict.fromkeys(
        FEATURES_LEVEL + FEATURES_RATE
    )
)

REQUIRED_COLUMNS = {
    "incident_id",
    "opened_at",
    "priority_code",
    "configuration_item",
    "parent_incident_id",
}


def _validate_silver(
    frame: pd.DataFrame,
) -> None:
    missing = (
        REQUIRED_COLUMNS
        - set(frame.columns)
    )

    if missing:
        raise ValueError(
            "Silver sem colunas obrigatorias "
            f"para ML v3.2: {sorted(missing)}"
        )

    if frame.empty:
        raise ValueError("Silver vazia.")


def _prepare_silver(
    frame: pd.DataFrame,
) -> pd.DataFrame:
    _validate_silver(frame)

    result = frame.copy()

    result["opened_at"] = pd.to_datetime(
        result["opened_at"],
        errors="coerce",
    )

    result = result.dropna(
        subset=["opened_at"]
    ).copy()

    result["day"] = (
        result["opened_at"]
        .dt.normalize()
    )

    result["priority_code"] = (
        pd.to_numeric(
            result["priority_code"],
            errors="coerce",
        )
        .astype("Int64")
    )

    return result


def _calendar_features(
    index: pd.DatetimeIndex,
) -> pd.DataFrame:
    years = sorted(
        set(index.year.tolist())
    )

    br = holidays.Brazil(
        years=years
    )

    result = pd.DataFrame(
        index=index
    )

    dow = index.dayofweek

    for value in range(7):
        result[
            f"dow_{value}"
        ] = (
            dow == value
        ).astype(int)

    result["is_weekend"] = (
        dow >= 5
    ).astype(int)

    result["is_holiday"] = [
        int(day in br)
        for day in index
    ]

    result["black_week"] = 0

    for year in years:
        november = pd.date_range(
            f"{year}-11-01",
            f"{year}-11-30",
            freq="D",
        )

        fridays = november[
            november.dayofweek == 4
        ]

        if len(fridays) >= 4:
            black_friday = fridays[3]

            mask = (
                (
                    index
                    >= black_friday
                    - pd.Timedelta(days=1)
                )
                & (
                    index
                    <= black_friday
                    + pd.Timedelta(days=4)
                )
            )

            result.loc[
                mask,
                "black_week",
            ] = 1

    result["dec_season"] = (
        (index.month == 12)
        & (index.day >= 15)
    ).astype(int)

    return result


def build_context(
    silver: pd.DataFrame,
) -> dict[str, Any]:
    base = _prepare_silver(
        silver
    )

    last_date = base[
        "day"
    ].max()

    base = base.loc[
        base["day"].between(
            MODEL_START_DATE,
            last_date,
        )
    ].copy()

    parent = (
        base["parent_incident_id"]
        .astype("string")
        .str.strip()
    )

    root = base.loc[
        parent.isna()
        | parent.eq("")
    ].copy()

    index = pd.date_range(
        MODEL_START_DATE,
        last_date
        + pd.Timedelta(days=7),
        freq="D",
    )

    observed = index[
        index <= last_date
    ]

    series = {}

    for scope, priority in (
        SCOPES.items()
    ):
        scoped = root

        if priority is not None:
            scoped = root.loc[
                root[
                    "priority_code"
                ].eq(priority)
            ]

        daily = (
            scoped.groupby("day")
            .size()
            .reindex(index)
            .astype(float)
        )

        daily.loc[
            observed
        ] = (
            daily.loc[
                observed
            ].fillna(0.0)
        )

        series[scope] = daily

    active_cis = (
        base.groupby("day")[
            "configuration_item"
        ]
        .nunique()
        .reindex(index)
        .astype(float)
    )

    active_cis.loc[
        observed
    ] = (
        active_cis.loc[
            observed
        ].fillna(0.0)
    )

    active_cis = (
        active_cis.ffill()
    )

    return {
        "last_date": last_date,
        "series": series,
        "active_cis": active_cis,
        "calendar": (
            _calendar_features(index)
        ),
    }


def build_features(
    y: pd.Series,
    horizon_days: int,
    context: dict[str, Any],
) -> pd.DataFrame:
    shifted = y.shift(
        horizon_days
    )

    x = pd.DataFrame(
        index=y.index
    )

    x["seas_lag7"] = (
        y.shift(7)
    )

    x["seas_lag14"] = (
        y.shift(14)
    )

    x["last"] = shifted

    x["roll7_mean"] = (
        shifted
        .rolling(7)
        .mean()
    )

    x["roll7_std"] = (
        shifted
        .rolling(7)
        .std()
    )

    x["roll28_mean"] = (
        shifted
        .rolling(28)
        .mean()
    )

    active_cis = context[
        "active_cis"
    ]

    x["exp_last"] = (
        active_cis.shift(
            horizon_days
        )
    )

    x["exp_roll7"] = (
        active_cis
        .shift(horizon_days)
        .rolling(7)
        .mean()
    )

    x["trend"] = np.arange(
        len(y),
        dtype=float,
    )

    exposure = (
        x["exp_roll7"]
        .replace(0, np.nan)
    )

    exposure_last = (
        x["exp_last"]
        .replace(0, np.nan)
    )

    x["r_last"] = (
        x["last"]
        / exposure_last
    )

    x["r_roll7"] = (
        x["roll7_mean"]
        / exposure
    )

    x["r_seas7"] = (
        x["seas_lag7"]
        / exposure
    )

    return x.join(
        context["calendar"]
    )


def _base_prediction(
    name: str,
    y: pd.Series,
    horizon_days: int,
    target_date: pd.Timestamp,
) -> float:
    if name == "naive7":
        values = y.shift(7)

    elif name == "media7":
        values = (
            y.shift(horizon_days)
            .rolling(7)
            .mean()
        )

    elif name == "ultimo":
        values = y.shift(
            horizon_days
        )

    else:
        raise ValueError(
            f"Regra desconhecida: {name}"
        )

    return max(
        0.0,
        float(
            values.loc[
                target_date
            ]
        ),
    )


def _model_prediction(
    name: str,
    model: Any,
    row: pd.DataFrame,
) -> float:
    if isinstance(
        model,
        dict,
    ):
        return max(
            0.0,
            float(
                model["constant"]
            ),
        )

    if name == "poisson_off":
        exposure = max(
            1e-6,
            float(
                row[
                    "exp_roll7"
                ].iloc[0]
            ),
        )

        rate = float(
            model.predict(
                row[
                    FEATURES_RATE
                ]
            )[0]
        )

        return max(
            0.0,
            rate * exposure,
        )

    return max(
        0.0,
        float(
            model.predict(
                row[
                    FEATURES_LEVEL
                ]
            )[0]
        ),
    )


def _scale(
    value: float,
) -> float:
    return max(
        1.0,
        float(
            np.sqrt(
                max(value, 0.0)
            )
        ),
    )


def load_volume_bundle(
    path,
) -> dict[str, Any]:
    bundle = joblib.load(path)

    if not isinstance(
        bundle,
        dict,
    ):
        raise ValueError(
            "Bundle ML invalido."
        )

    if "components" not in bundle:
        raise ValueError(
            "Bundle sem components."
        )

    return bundle


def predict_volume(
    silver: pd.DataFrame,
    bundle: dict[str, Any],
    *,
    generated_at: datetime | None = None,
) -> pd.DataFrame:
    context = build_context(
        silver
    )

    generated_at = (
        generated_at
        or datetime.now(UTC)
    )

    rows = []

    for scope, y in (
        context["series"].items()
    ):
        for (
            horizon,
            horizon_days,
        ) in HORIZONS.items():
            key = (
                f"{scope}|{horizon}"
            )

            component = (
                bundle["components"]
                .get(key)
            )

            if not component:
                raise ValueError(
                    "Bundle sem componente "
                    f"{key}."
                )

            target_date = (
                context["last_date"]
                + pd.Timedelta(
                    days=horizon_days
                )
            )

            x = build_features(
                y,
                horizon_days,
                context,
            )

            row = x.loc[
                [target_date]
            ]

            if (
                row[
                    ALL_FEATURES
                ]
                .isna()
                .any()
                .any()
            ):
                raise ValueError(
                    "Features invalidas "
                    f"para {key}."
                )

            predictor = str(
                component[
                    "predictor"
                ]
            )

            if predictor in BASES:
                prediction = (
                    _base_prediction(
                        predictor,
                        y,
                        horizon_days,
                        target_date,
                    )
                )
            else:
                prediction = (
                    _model_prediction(
                        predictor,
                        component[
                            "model"
                        ],
                        row,
                    )
                )

            q_low = float(
                component[
                    "q_low"
                ]
            )

            q_high = float(
                component[
                    "q_high"
                ]
            )

            lower = max(
                0.0,
                prediction
                + q_low
                * _scale(prediction),
            )

            upper = max(
                lower,
                prediction
                + q_high
                * _scale(prediction),
            )

            rows.append(
                {
                    "reference_date":
                        target_date,
                    "generated_at":
                        generated_at.replace(
                            tzinfo=None
                        ),
                    "horizon":
                        horizon,
                    "priority_scope":
                        scope,
                    "predicted_incident_count":
                        round(
                            prediction,
                            2,
                        ),
                    "lower_bound":
                        round(
                            lower,
                            2,
                        ),
                    "upper_bound":
                        round(
                            upper,
                            2,
                        ),
                    "model_name":
                        predictor,
                    "model_version":
                        str(
                            bundle[
                                "model_version"
                            ]
                        ),
                }
            )

    return (
        pd.DataFrame(rows)
        .sort_values(
            [
                "priority_scope",
                "horizon",
            ]
        )
        .reset_index(drop=True)
    )
