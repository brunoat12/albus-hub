from __future__ import annotations

import argparse
import json
import os

from albus_hub.config import get_settings
from albus_hub.storage import BackupService
from albus_hub.storage.adls import sync_directory


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Executa backup dos dados do Albus-Hub.")

    parser.add_argument(
        "--type",
        choices=[
            "auto",
            "full",
            "incremental",
        ],
        default="auto",
        help="Tipo de backup a executar.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = get_settings()

    backup_root = settings.absolute_path(settings.data_backup_path)

    service = BackupService(
        backup_root=backup_root,
        sources={
            "raw": settings.absolute_path(settings.data_raw_path),
            "bronze": settings.absolute_path(settings.data_bronze_path),
            "silver": settings.absolute_path(settings.data_silver_path),
            "gold": settings.absolute_path(settings.data_gold_path),
            "quality": settings.absolute_path(settings.artifact_path / "quality"),
        },
        retention_days=settings.backup_retention_days,
        full_interval_days=settings.backup_full_interval_days,
    )

    report = service.create_backup(mode=args.type)

    backup_file_system = os.getenv(
        "AZURE_BACKUP_FILE_SYSTEM",
        "backup",
    )

    backup_remote_prefix = os.getenv(
        "AZURE_BACKUP_PREFIX",
        "albus-hub/dev",
    )

    cloud_report = sync_directory(
        local_root=backup_root,
        file_system=backup_file_system,
        remote_prefix=backup_remote_prefix,
    )

    report["cloud_backup"] = cloud_report

    print(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
