from __future__ import annotations

import json

from albus_hub.config import get_settings
from albus_hub.ingestion.locaweb import run_ingestion


def main() -> None:
    settings = get_settings()

    report = run_ingestion(
        source_path=settings.absolute_path(settings.locaweb_source_file),
        bronze_path=settings.absolute_path(settings.locaweb_bronze_file),
        silver_path=settings.absolute_path(settings.locaweb_silver_file),
        report_path=settings.absolute_path(settings.locaweb_quality_report),
        sheet_name=settings.locaweb_sheet_name,
    )

    print(json.dumps(report, ensure_ascii=False, indent=2))

    if report["quality_status"] == "failed":
        raise SystemExit("A ingestão terminou com erros bloqueantes.")


if __name__ == "__main__":
    main()
