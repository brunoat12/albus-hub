from __future__ import annotations

from collections.abc import Sequence

import pandas as pd

ELIGIBILITY_COLUMN = "entered_kpi_source"
TARGET_COLUMN = "kpi_breached_source"

IDENTIFIER_COLUMNS = ["incident_id", "opened_at"]

BASE_CATEGORICAL_FEATURES = [
    "priority_code",
    "product",
    "category",
    "subcategory",
    "assigned_group",
    "configuration_item",
    "opened_by",
]

TEMPORAL_FEATURES = [
    "opened_hour",
    "opened_day_of_week",
    "opened_month",
    "is_weekend",
]

HISTORICAL_FEATURES = [
    "assigned_group_incidents_previous_1d",
    "assigned_group_incidents_previous_7d",
    "assigned_group_incidents_previous_30d",
    "assigned_group_known_outcomes_previous_30d",
    "assigned_group_breaches_previous_30d",
    "assigned_group_breach_rate_previous_30d",
    "product_incidents_previous_7d",
    "category_incidents_previous_7d",
    "priority_incidents_previous_7d",
]

CATEGORICAL_FEATURES = BASE_CATEGORICAL_FEATURES
NUMERIC_FEATURES = TEMPORAL_FEATURES + HISTORICAL_FEATURES
MODEL_FEATURES = CATEGORICAL_FEATURES + NUMERIC_FEATURES

LEAKAGE_COLUMNS = [
    "resolved_at",
    "closed_at",
    "duration_seconds",
    "duration_hours",
    "calculated_duration_seconds",
    "duration_difference_seconds",
    "duration_mismatch",
    "closure_code",
    "solution_type",
    "status",
    ELIGIBILITY_COLUMN,
    TARGET_COLUMN,
    "entered_kpi_raw",
    "kpi_breached_raw",
    "entered_kpi_recalculated_raw",
    "kpi_breached_recalculated_raw",
    "entered_kpi_rule_mismatch",
    "kpi_breached_rule_mismatch",
]

REQUIRED_SILVER_COLUMNS = {
    "incident_id",
    "opened_at",
    "closed_at",
    "priority_code",
    "product",
    "category",
    "subcategory",
    "assigned_group",
    "configuration_item",
    "opened_by",
    ELIGIBILITY_COLUMN,
    TARGET_COLUMN,
}


class RiskDataContractError(ValueError):
    """Indica que a Silver não permite construir o modelo de risco com segurança."""


def validate_silver_for_risk(frame: pd.DataFrame, *, require_targets: bool = True) -> None:
    """Valida os requisitos mínimos da Silver para treino e inferência histórica."""
    missing = REQUIRED_SILVER_COLUMNS - set(frame.columns)
    if missing:
        raise RiskDataContractError(f"Colunas obrigatórias ausentes: {sorted(missing)}")

    if frame["incident_id"].isna().any() or frame["incident_id"].duplicated().any():
        raise RiskDataContractError("incident_id deve ser preenchido e único.")

    opened_at = pd.to_datetime(frame["opened_at"], errors="coerce")
    if opened_at.isna().any():
        raise RiskDataContractError("opened_at deve ser preenchido e válido.")

    if require_targets:
        eligible = frame[ELIGIBILITY_COLUMN].eq(True)
        if not eligible.any():
            raise RiskDataContractError("A Silver não possui incidentes elegíveis ao KPI.")

        invalid_target = eligible & frame[TARGET_COLUMN].isna()
        if invalid_target.any():
            raise RiskDataContractError("Incidentes elegíveis possuem target nulo.")


def assert_no_leakage(feature_columns: Sequence[str]) -> None:
    """Bloqueia qualquer tentativa de incluir colunas pós-desfecho no modelo."""
    forbidden = sorted(set(feature_columns) & set(LEAKAGE_COLUMNS))
    if forbidden:
        raise RiskDataContractError(f"Features proibidas por leakage: {forbidden}")
