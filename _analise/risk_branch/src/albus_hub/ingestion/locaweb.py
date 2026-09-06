from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

SOURCE_COLUMNS = [
    "Número",
    "Prioridade",
    "Produto",
    "Categoria",
    "Subcategoria",
    "Grupo designado",
    "Item de configuração",
    "Aberto",
    "Resolvido",
    "Encerrado",
    "Duração",
    "Código de fechamento",
    "Descrição resumida",
    "Solução",
    "Aberto por",
    "Incidente Pai",
    "Status",
    "Entrou para KPI?",
    "KPI Violado?",
]

COLUMN_MAP = {
    "Número": "incident_id",
    "Prioridade": "priority_raw",
    "Produto": "product",
    "Categoria": "category",
    "Subcategoria": "subcategory",
    "Grupo designado": "assigned_group",
    "Item de configuração": "configuration_item",
    "Aberto": "opened_at",
    "Resolvido": "resolved_at",
    "Encerrado": "closed_at",
    "Duração": "duration_seconds",
    "Código de fechamento": "closure_code",
    "Descrição resumida": "short_description",
    "Solução": "solution_type",
    "Aberto por": "opened_by",
    "Incidente Pai": "parent_incident_id",
    "Status": "status",
    "Entrou para KPI?": "entered_kpi_raw",
    "KPI Violado?": "kpi_breached_raw",
}

TEXT_COLUMNS = [
    "incident_id",
    "priority_raw",
    "product",
    "category",
    "subcategory",
    "assigned_group",
    "configuration_item",
    "closure_code",
    "short_description",
    "solution_type",
    "opened_by",
    "parent_incident_id",
    "status",
    "entered_kpi_raw",
    "kpi_breached_raw",
]

SLA_SECONDS = {
    1: 4 * 60 * 60,
    2: 4 * 60 * 60,
    3: 12 * 60 * 60,
    4: 24 * 60 * 60,
    5: 96 * 60 * 60,
}


def clean_text(series: pd.Series) -> pd.Series:
    """Padroniza texto e converte strings vazias em nulo."""
    return series.astype("string").str.strip().replace("", pd.NA)


def read_source(path: Path, sheet_name: str) -> pd.DataFrame:
    """Lê e valida o schema exato da planilha fornecida pela Locaweb."""
    frame = pd.read_excel(
        path,
        sheet_name=sheet_name,
        engine="openpyxl",
        keep_default_na=False,
    )
    frame.columns = [str(column).strip() for column in frame.columns]

    missing = sorted(set(SOURCE_COLUMNS) - set(frame.columns))
    unexpected = sorted(set(frame.columns) - set(SOURCE_COLUMNS))

    if missing or unexpected:
        raise ValueError(f"Schema inválido. Ausentes: {missing}; não esperadas: {unexpected}")

    return frame[SOURCE_COLUMNS].copy()


def build_silver(bronze: pd.DataFrame) -> pd.DataFrame:
    """Cria a camada Silver, preservando os indicadores originais de KPI."""
    frame = bronze.rename(columns=COLUMN_MAP).copy()

    for column in TEXT_COLUMNS:
        frame[column] = clean_text(frame[column])

    for column in ["opened_at", "resolved_at", "closed_at"]:
        frame[column] = pd.to_datetime(
            frame[column],
            errors="coerce",
            dayfirst=True,
        )

    frame["duration_seconds"] = (
        pd.to_numeric(frame["duration_seconds"], errors="coerce").round().astype("Int64")
    )
    frame["priority_code"] = (
        frame["priority_raw"]
        .str.extract(r"^([1-5])", expand=False)
        .pipe(pd.to_numeric, errors="coerce")
        .astype("Int64")
    )
    frame["priority_label"] = frame["priority_raw"].str.split(" - ", n=1).str[-1]

    frame["entered_kpi_source"] = (
        frame["entered_kpi_raw"].map({"SIM": True, "NAO": False}).astype("boolean")
    )
    frame["kpi_breached_source"] = (
        frame["kpi_breached_raw"].map({"SIM": True, "NAO": False, "N/A": pd.NA}).astype("boolean")
    )

    frame["has_parent_incident"] = frame["parent_incident_id"].notna()
    frame["is_no_intervention"] = frame["status"].eq("Sem Intervenção")
    frame["is_monitoring_opened"] = frame["opened_by"].eq("Monitoramento")
    frame["sla_limit_seconds"] = frame["priority_code"].map(SLA_SECONDS).astype("Int64")
    frame["duration_hours"] = frame["duration_seconds"] / 3600

    frame["opened_date"] = frame["opened_at"].dt.normalize()
    frame["opened_year"] = frame["opened_at"].dt.year.astype("Int64")
    frame["opened_month"] = frame["opened_at"].dt.month.astype("Int64")
    frame["opened_day_of_week"] = frame["opened_at"].dt.dayofweek.astype("Int64")
    frame["opened_hour"] = frame["opened_at"].dt.hour.astype("Int64")

    duration_end = frame["resolved_at"].fillna(frame["closed_at"])
    frame["calculated_duration_seconds"] = (duration_end - frame["opened_at"]).dt.total_seconds()
    frame["duration_difference_seconds"] = (
        frame["duration_seconds"].astype("Float64") - frame["calculated_duration_seconds"]
    ).abs()
    frame["duration_mismatch"] = (frame["duration_difference_seconds"] > 2).fillna(False)

    expected_entry = (
        frame["priority_code"].isin([1, 2, 3])
        & ~frame["has_parent_incident"]
        & ~frame["is_no_intervention"]
    )
    frame["entered_kpi_recalculated_raw"] = expected_entry.map({True: "SIM", False: "NAO"})

    expected_breach = pd.Series("N/A", index=frame.index, dtype="string")
    comparable = (
        expected_entry & frame["duration_seconds"].notna() & frame["sla_limit_seconds"].notna()
    )
    expected_breach.loc[comparable & (frame["duration_seconds"] <= frame["sla_limit_seconds"])] = (
        "NAO"
    )
    expected_breach.loc[comparable & (frame["duration_seconds"] > frame["sla_limit_seconds"])] = (
        "SIM"
    )

    frame["kpi_breached_recalculated_raw"] = expected_breach
    frame["entered_kpi_rule_mismatch"] = frame["entered_kpi_raw"].ne(
        frame["entered_kpi_recalculated_raw"]
    )
    frame["kpi_breached_rule_mismatch"] = frame["kpi_breached_raw"].ne(
        frame["kpi_breached_recalculated_raw"]
    )

    return frame


def build_report(frame: pd.DataFrame) -> dict[str, object]:
    """Cria relatório de qualidade com erros bloqueantes e alertas."""
    mandatory = [
        "incident_id",
        "priority_raw",
        "assigned_group",
        "opened_at",
        "closed_at",
        "duration_seconds",
        "short_description",
        "opened_by",
        "status",
        "entered_kpi_raw",
        "kpi_breached_raw",
    ]

    blocking = {
        "mandatory_nulls": int(frame[mandatory].isna().sum().sum()),
        "duplicate_incident_ids": int(frame["incident_id"].duplicated().sum()),
        "invalid_incident_ids": int(
            (~frame["incident_id"].str.fullmatch(r"INC\d{7}", na=False)).sum()
        ),
        "closed_before_opened": int((frame["closed_at"] < frame["opened_at"]).sum()),
        "negative_duration": int((frame["duration_seconds"] < 0).sum()),
    }

    warnings = {
        "resolved_after_closed": int((frame["resolved_at"] > frame["closed_at"]).sum()),
        "duration_mismatch": int(frame["duration_mismatch"].sum()),
        "subcategory_without_category": int(
            (frame["subcategory"].notna() & frame["category"].isna()).sum()
        ),
        "entered_kpi_rule_mismatch": int(frame["entered_kpi_rule_mismatch"].sum()),
        "kpi_breached_rule_mismatch": int(frame["kpi_breached_rule_mismatch"].sum()),
    }

    monthly = (
        frame.dropna(subset=["opened_at"]).groupby(frame["opened_at"].dt.to_period("M")).size()
    )

    return {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "quality_status": (
            "failed"
            if sum(blocking.values())
            else "passed_with_warnings"
            if sum(warnings.values())
            else "passed"
        ),
        "row_count": int(len(frame)),
        "opened_at_min": frame["opened_at"].min().isoformat(),
        "opened_at_max": frame["opened_at"].max().isoformat(),
        "blocking_checks": blocking,
        "warning_checks": warnings,
        "null_percentage": {
            column: round(float(frame[column].isna().mean() * 100), 3)
            for column in COLUMN_MAP.values()
        },
        "priority_distribution": {
            str(key): int(value) for key, value in frame["priority_raw"].value_counts().items()
        },
        "status_distribution": {
            str(key): int(value) for key, value in frame["status"].value_counts().items()
        },
        "entered_kpi_distribution": {
            str(key): int(value) for key, value in frame["entered_kpi_raw"].value_counts().items()
        },
        "kpi_breached_distribution": {
            str(key): int(value) for key, value in frame["kpi_breached_raw"].value_counts().items()
        },
        "monthly_volume": {str(period): int(value) for period, value in monthly.items()},
    }


def run_ingestion(
    source_path: Path,
    bronze_path: Path,
    silver_path: Path,
    report_path: Path,
    sheet_name: str = "Dataset Geral",
) -> dict[str, object]:
    """Executa leitura, Bronze, Silver e relatório de qualidade."""
    source = read_source(source_path, sheet_name)

    bronze = source.copy()

    date_columns = [
        "Aberto",
        "Resolvido",
        "Encerrado",
    ]

    for column in date_columns:
        bronze[column] = pd.to_datetime(
            bronze[column].replace("", pd.NA),
            errors="coerce",
            dayfirst=True,
        )

    bronze["Duração"] = (
        pd.to_numeric(
            bronze["Duração"].replace("", pd.NA),
            errors="coerce",
        )
        .round()
        .astype("Int64")
    )

    non_text_columns = set(date_columns + ["Duração"])

    for column in SOURCE_COLUMNS:
        if column not in non_text_columns:
            bronze[column] = bronze[column].astype("string").str.strip().replace("", pd.NA)

    bronze["_source_file"] = source_path.name
    bronze["_source_row_number"] = range(2, len(bronze) + 2)
    bronze["_ingested_at_utc"] = datetime.now(UTC)

    silver = build_silver(bronze)
    report = build_report(silver)

    for path in [bronze_path, silver_path, report_path]:
        path.parent.mkdir(parents=True, exist_ok=True)

    bronze.to_parquet(bronze_path, index=False)
    silver.to_parquet(silver_path, index=False)

    with report_path.open("w", encoding="utf-8") as file:
        json.dump(report, file, ensure_ascii=False, indent=2)

    return report
