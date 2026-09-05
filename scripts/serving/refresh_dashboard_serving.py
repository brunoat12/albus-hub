from __future__ import annotations

import os
from pathlib import Path

import pandas as pd

from albus_hub.config.settings import get_settings
from albus_hub.storage.adls import download_file
from albus_hub.storage.mysql import (
    MySQLRepository,
    create_mysql_engine,
)

STORAGE_ACCOUNT_ENV = "AZURE_STORAGE_ACCOUNT_NAME"

GOLD_FILE_SYSTEM = "gold"

VOLUME_REMOTE_PATH = "analytics/daily_incident_volume.parquet"

BREAKDOWN_REMOTE_PATH = "analytics/daily_incident_breakdown.parquet"

RUNTIME_DIR = Path("artifacts/runtime/dashboard_serving")

LOCAL_VOLUME_PATH = RUNTIME_DIR / "daily_incident_volume.parquet"

LOCAL_BREAKDOWN_PATH = RUNTIME_DIR / "daily_incident_breakdown.parquet"


def normalize_volume(
    frame: pd.DataFrame,
) -> list[dict]:
    result = frame.copy()

    result["reference_date"] = pd.to_datetime(result["reference_date"]).dt.date

    numeric_columns = [
        "incident_count",
        "entered_kpi_count",
        "kpi_breach_count",
        "monitoring_incident_count",
        "no_intervention_count",
    ]

    for column in numeric_columns:
        result[column] = (
            pd.to_numeric(
                result[column],
                errors="raise",
            )
            .fillna(0)
            .astype(int)
        )

    return result.to_dict(orient="records")


def normalize_breakdown(
    frame: pd.DataFrame,
) -> list[dict]:
    result = frame.copy()

    result["reference_date"] = pd.to_datetime(result["reference_date"]).dt.date

    text_columns = [
        "dimension_name",
        "dimension_value",
        "priority_scope",
    ]

    for column in text_columns:
        result[column] = result[column].astype("string").fillna("N/A").astype(str)

    numeric_columns = [
        "incident_count",
        "entered_kpi_count",
        "kpi_breach_count",
    ]

    for column in numeric_columns:
        result[column] = (
            pd.to_numeric(
                result[column],
                errors="raise",
            )
            .fillna(0)
            .astype(int)
        )

    return result.to_dict(orient="records")


def main() -> None:
    if not os.getenv(STORAGE_ACCOUNT_ENV):
        raise RuntimeError(f"{STORAGE_ACCOUNT_ENV} não está configurada.")

    RUNTIME_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    print("=== REFRESH DASHBOARD SERVING ===")

    print("Baixando Gold analítico do ADLS...")

    download_file(
        file_system=GOLD_FILE_SYSTEM,
        remote_path=VOLUME_REMOTE_PATH,
        local_path=LOCAL_VOLUME_PATH,
    )

    download_file(
        file_system=GOLD_FILE_SYSTEM,
        remote_path=BREAKDOWN_REMOTE_PATH,
        local_path=LOCAL_BREAKDOWN_PATH,
    )

    volume = pd.read_parquet(LOCAL_VOLUME_PATH)

    breakdown = pd.read_parquet(LOCAL_BREAKDOWN_PATH)

    print(
        "Volume:",
        len(volume),
        "linhas",
    )

    print(
        "Breakdown:",
        len(breakdown),
        "linhas",
    )

    settings = get_settings()

    repository = MySQLRepository(create_mysql_engine(settings))

    repository.ensure_dashboard_serving_tables()

    print()
    print("Atualizando app_daily_incident_volume...")

    repository.replace_daily_incident_volume(normalize_volume(volume))

    print("Atualizando app_daily_incident_breakdown...")

    repository.replace_daily_incident_breakdown(normalize_breakdown(breakdown))

    print()
    print("DASHBOARD_SERVING_REFRESH=SUCCESS")


if __name__ == "__main__":
    main()
