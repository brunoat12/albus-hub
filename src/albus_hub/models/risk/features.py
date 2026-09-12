from __future__ import annotations

import numpy as np
import pandas as pd

from albus_hub.models.risk.contracts import (
    ELIGIBILITY_COLUMN,
    MODEL_FEATURES,
    TARGET_COLUMN,
    validate_silver_for_risk,
)


def _strict_previous_counts(
    frame: pd.DataFrame,
    key: str,
    window_days: int,
) -> np.ndarray:
    """Conta aberturas anteriores na janela, excluindo timestamps simultâneos."""
    result = np.zeros(len(frame), dtype=np.int32)
    window = np.timedelta64(window_days, "D")

    for positions in frame.groupby(key, dropna=False, sort=False).indices.values():
        positions = np.asarray(positions, dtype=np.int64)
        times = frame.iloc[positions]["opened_at"].to_numpy(dtype="datetime64[ns]")
        left = np.searchsorted(times, times - window, side="left")
        right = np.searchsorted(times, times, side="left")
        result[positions] = right - left

    return result


def _known_group_outcomes_previous_30d(frame: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """Usa somente desfechos encerrados antes da abertura do incidente corrente."""
    known_count = np.zeros(len(frame), dtype=np.int32)
    breach_count = np.zeros(len(frame), dtype=np.int32)
    window = np.timedelta64(30, "D")

    outcome_events = frame.loc[
        frame[ELIGIBILITY_COLUMN].eq(True)
        & frame[TARGET_COLUMN].notna()
        & frame["closed_at"].notna(),
        ["assigned_group", "closed_at", TARGET_COLUMN],
    ].copy()
    outcome_events["closed_at"] = pd.to_datetime(outcome_events["closed_at"])

    for group, positions in frame.groupby(
        "assigned_group", dropna=False, sort=False
    ).indices.items():
        positions = np.asarray(positions, dtype=np.int64)
        opened = frame.iloc[positions]["opened_at"].to_numpy(dtype="datetime64[ns]")
        if pd.isna(group):
            events = outcome_events.loc[outcome_events["assigned_group"].isna()]
        else:
            events = outcome_events.loc[outcome_events["assigned_group"].eq(group)]
        events = events.sort_values("closed_at", kind="stable")
        event_times = events["closed_at"].to_numpy(dtype="datetime64[ns]")
        event_targets = events[TARGET_COLUMN].astype(np.int32).to_numpy()
        cumulative_breaches = np.concatenate(([0], np.cumsum(event_targets)))

        left = np.searchsorted(event_times, opened - window, side="left")
        right = np.searchsorted(event_times, opened, side="left")
        known_count[positions] = right - left
        breach_count[positions] = cumulative_breaches[right] - cumulative_breaches[left]

    return known_count, breach_count


def build_risk_features(
    silver: pd.DataFrame,
    *,
    require_targets: bool = True,
) -> pd.DataFrame:
    """Cria features disponíveis na abertura e históricos estritamente anteriores."""
    validate_silver_for_risk(silver, require_targets=require_targets)
    frame = silver.copy()
    frame["opened_at"] = pd.to_datetime(frame["opened_at"])
    frame["closed_at"] = pd.to_datetime(frame["closed_at"], errors="coerce")
    frame = frame.sort_values(["opened_at", "incident_id"], kind="stable").reset_index(drop=True)

    frame["opened_hour"] = frame["opened_at"].dt.hour.astype("int16")
    frame["opened_day_of_week"] = frame["opened_at"].dt.dayofweek.astype("int16")
    frame["opened_month"] = frame["opened_at"].dt.month.astype("int16")
    frame["is_weekend"] = frame["opened_day_of_week"].isin([5, 6]).astype("int8")

    for days in (1, 7, 30):
        frame[f"assigned_group_incidents_previous_{days}d"] = _strict_previous_counts(
            frame, "assigned_group", days
        )
    frame["product_incidents_previous_7d"] = _strict_previous_counts(frame, "product", 7)
    frame["category_incidents_previous_7d"] = _strict_previous_counts(frame, "category", 7)
    frame["priority_incidents_previous_7d"] = _strict_previous_counts(frame, "priority_code", 7)

    known, breached = _known_group_outcomes_previous_30d(frame)
    frame["assigned_group_known_outcomes_previous_30d"] = known
    frame["assigned_group_breaches_previous_30d"] = breached
    frame["assigned_group_breach_rate_previous_30d"] = np.divide(
        breached,
        known,
        out=np.full(len(frame), np.nan, dtype=np.float64),
        where=known > 0,
    )

    output_columns = [
        "incident_id",
        "opened_at",
        ELIGIBILITY_COLUMN,
        TARGET_COLUMN,
        *MODEL_FEATURES,
    ]
    return frame[output_columns].copy()
