from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

PRIORITY_SCOPES: dict[str, int | None] = {
    "ALL": None,
    "P2": 2,
    "P3": 3,
}

BREAKDOWN_DIMENSIONS = [
    "assigned_group",
    "product",
    "category",
    "configuration_item",
]

REQUIRED_COLUMNS = [
    "incident_id",
    "opened_at",
    "priority_code",
    "assigned_group",
    "product",
    "category",
    "configuration_item",
    "entered_kpi_source",
    "kpi_breached_source",
    "opened_by",
    "status",
]

MAIN_COUNT_COLUMNS = [
    "incident_count",
    "entered_kpi_count",
    "kpi_breach_count",
    "monitoring_incident_count",
    "no_intervention_count",
]

BREAKDOWN_COUNT_COLUMNS = [
    "incident_count",
    "entered_kpi_count",
    "kpi_breach_count",
]

MISSING_DIMENSION_VALUE = "__MISSING__"


def _validate_silver(frame: pd.DataFrame) -> None:
    """Valida as colunas necessárias para construir a Gold."""
    missing = sorted(set(REQUIRED_COLUMNS) - set(frame.columns))

    if missing:
        raise ValueError(f"Silver sem colunas obrigatórias: {missing}")

    if frame.empty:
        raise ValueError("A camada Silver está vazia.")


def _prepare_base(frame: pd.DataFrame) -> pd.DataFrame:
    """Prepara os campos usados nas agregações."""
    _validate_silver(frame)

    base = frame[REQUIRED_COLUMNS].copy()

    base["opened_at"] = pd.to_datetime(
        base["opened_at"],
        errors="coerce",
    )

    base = base.dropna(subset=["opened_at"]).copy()

    if base.empty:
        raise ValueError("Nenhum registro possui opened_at válido.")

    base["reference_date"] = base["opened_at"].dt.normalize()

    base["priority_code"] = pd.to_numeric(
        base["priority_code"],
        errors="coerce",
    ).astype("Int64")

    base["_entered_kpi"] = base["entered_kpi_source"].fillna(False).astype(bool)

    base["_kpi_breach"] = base["kpi_breached_source"].fillna(False).astype(bool)

    base["_monitoring"] = base["opened_by"].astype("string").eq("Monitoramento").fillna(False)

    base["_no_intervention"] = base["status"].astype("string").eq("Sem Intervenção").fillna(False)

    return base


def _filter_priority_scope(
    frame: pd.DataFrame,
    priority_code: int | None,
) -> pd.DataFrame:
    """Aplica o escopo ALL, P2 ou P3."""
    if priority_code is None:
        return frame

    return frame.loc[frame["priority_code"].eq(priority_code)]


def build_daily_volume(
    silver: pd.DataFrame,
) -> pd.DataFrame:
    """Cria a série diária contínua para ALL, P2 e P3."""
    base = _prepare_base(silver)

    full_dates = pd.date_range(
        start=base["reference_date"].min(),
        end=base["reference_date"].max(),
        freq="D",
    )

    parts: list[pd.DataFrame] = []

    for scope, priority_code in PRIORITY_SCOPES.items():
        scoped = _filter_priority_scope(
            base,
            priority_code,
        )

        grouped = (
            scoped.groupby("reference_date")
            .agg(
                incident_count=("incident_id", "size"),
                entered_kpi_count=(
                    "_entered_kpi",
                    "sum",
                ),
                kpi_breach_count=(
                    "_kpi_breach",
                    "sum",
                ),
                monitoring_incident_count=(
                    "_monitoring",
                    "sum",
                ),
                no_intervention_count=(
                    "_no_intervention",
                    "sum",
                ),
            )
            .reindex(full_dates, fill_value=0)
            .rename_axis("reference_date")
            .reset_index()
        )

        grouped["priority_scope"] = scope
        parts.append(grouped)

    result = pd.concat(
        parts,
        ignore_index=True,
    )

    for column in MAIN_COUNT_COLUMNS:
        result[column] = result[column].astype("int64")

    return (
        result[
            [
                "reference_date",
                "priority_scope",
                *MAIN_COUNT_COLUMNS,
            ]
        ]
        .sort_values(
            [
                "reference_date",
                "priority_scope",
            ]
        )
        .reset_index(drop=True)
    )


def build_daily_breakdown(
    silver: pd.DataFrame,
) -> pd.DataFrame:
    """Cria cortes diários por dimensões operacionais."""
    base = _prepare_base(silver)
    parts: list[pd.DataFrame] = []

    for dimension in BREAKDOWN_DIMENSIONS:
        for scope, priority_code in PRIORITY_SCOPES.items():
            scoped = _filter_priority_scope(
                base,
                priority_code,
            ).copy()

            if scoped.empty:
                continue

            values = scoped[dimension].astype("string").str.strip()

            scoped["dimension_value"] = values.mask(
                values.isna() | values.eq(""),
                MISSING_DIMENSION_VALUE,
            )

            grouped = (
                scoped.groupby(
                    [
                        "reference_date",
                        "dimension_value",
                    ],
                    dropna=False,
                )
                .agg(
                    incident_count=(
                        "incident_id",
                        "size",
                    ),
                    entered_kpi_count=(
                        "_entered_kpi",
                        "sum",
                    ),
                    kpi_breach_count=(
                        "_kpi_breach",
                        "sum",
                    ),
                )
                .reset_index()
            )

            grouped["dimension_name"] = dimension
            grouped["priority_scope"] = scope

            parts.append(grouped)

    if not parts:
        return pd.DataFrame(
            columns=[
                "reference_date",
                "dimension_name",
                "dimension_value",
                "priority_scope",
                *BREAKDOWN_COUNT_COLUMNS,
            ]
        )

    result = pd.concat(
        parts,
        ignore_index=True,
    )

    for column in BREAKDOWN_COUNT_COLUMNS:
        result[column] = result[column].astype("int64")

    return (
        result[
            [
                "reference_date",
                "dimension_name",
                "dimension_value",
                "priority_scope",
                *BREAKDOWN_COUNT_COLUMNS,
            ]
        ]
        .sort_values(
            [
                "reference_date",
                "dimension_name",
                "dimension_value",
                "priority_scope",
            ]
        )
        .reset_index(drop=True)
    )


def build_gold_report(
    silver: pd.DataFrame,
    daily_volume: pd.DataFrame,
    breakdown: pd.DataFrame,
) -> dict[str, object]:
    """Gera relatório de qualidade e reconciliação."""
    base = _prepare_base(silver)

    source_by_scope = {
        scope: int(
            len(
                _filter_priority_scope(
                    base,
                    priority_code,
                )
            )
        )
        for scope, priority_code in (PRIORITY_SCOPES.items())
    }

    gold_by_scope = {
        scope: int(
            daily_volume.loc[
                daily_volume["priority_scope"].eq(scope),
                "incident_count",
            ].sum()
        )
        for scope in PRIORITY_SCOPES
    }

    reconciliation = {
        scope: {
            "source_count": source_by_scope[scope],
            "gold_count": gold_by_scope[scope],
            "matches": (source_by_scope[scope] == gold_by_scope[scope]),
        }
        for scope in PRIORITY_SCOPES
    }

    daily_duplicate_keys = int(
        daily_volume.duplicated(
            [
                "reference_date",
                "priority_scope",
            ]
        ).sum()
    )

    breakdown_duplicate_keys = int(
        breakdown.duplicated(
            [
                "reference_date",
                "dimension_name",
                "dimension_value",
                "priority_scope",
            ]
        ).sum()
    )

    daily_null_values = int(
        daily_volume[
            [
                "reference_date",
                "priority_scope",
                *MAIN_COUNT_COLUMNS,
            ]
        ]
        .isna()
        .sum()
        .sum()
    )

    breakdown_null_values = int(
        breakdown[
            [
                "reference_date",
                "dimension_name",
                "dimension_value",
                "priority_scope",
                *BREAKDOWN_COUNT_COLUMNS,
            ]
        ]
        .isna()
        .sum()
        .sum()
    )

    negative_counts = int(
        (daily_volume[MAIN_COUNT_COLUMNS] < 0).sum().sum()
        + (breakdown[BREAKDOWN_COUNT_COLUMNS] < 0).sum().sum()
    )

    reconciliation_failed = int(not all(item["matches"] for item in reconciliation.values()))

    checks = {
        "daily_duplicate_keys": (daily_duplicate_keys),
        "breakdown_duplicate_keys": (breakdown_duplicate_keys),
        "daily_null_values": daily_null_values,
        "breakdown_null_values": (breakdown_null_values),
        "negative_counts": negative_counts,
        "reconciliation_failed": (reconciliation_failed),
    }

    return {
        "generated_at_utc": (datetime.now(UTC).isoformat()),
        "quality_status": ("passed" if sum(checks.values()) == 0 else "failed"),
        "silver_rows_with_valid_opened_at": int(len(base)),
        "daily_volume_rows": int(len(daily_volume)),
        "daily_breakdown_rows": int(len(breakdown)),
        "reference_date_min": (daily_volume["reference_date"].min().isoformat()),
        "reference_date_max": (daily_volume["reference_date"].max().isoformat()),
        "checks": checks,
        "reconciliation": reconciliation,
    }


def run_daily_volume_gold(
    silver_path: Path,
    daily_volume_path: Path,
    breakdown_path: Path,
    report_path: Path,
) -> dict[str, object]:
    """Lê a Silver e grava os arquivos da Gold."""
    silver = pd.read_parquet(silver_path)

    daily_volume = build_daily_volume(silver)
    breakdown = build_daily_breakdown(silver)

    report = build_gold_report(
        silver,
        daily_volume,
        breakdown,
    )

    for path in [
        daily_volume_path,
        breakdown_path,
        report_path,
    ]:
        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

    daily_volume.to_parquet(
        daily_volume_path,
        index=False,
    )

    breakdown.to_parquet(
        breakdown_path,
        index=False,
    )

    with report_path.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            report,
            file,
            ensure_ascii=False,
            indent=2,
        )

    return report
