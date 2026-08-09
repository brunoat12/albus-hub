from __future__ import annotations

import argparse
import json

from albus_hub.config import get_settings
from albus_hub.storage import BackupService


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

    service = BackupService(
        backup_root=settings.absolute_path(settings.data_backup_path),
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

    print(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
