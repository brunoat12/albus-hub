from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from albus_hub.config import get_settings
from albus_hub.storage import RestoreService
from albus_hub.storage.adls import download_directory


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Restaura o backup mais recente do "
            "Albus-Hub a partir do ADLS."
        )
    )

    parser.add_argument(
        "--destination",
        type=Path,
        default=Path("data/restore_test"),
        help="Diretório onde os dados serão restaurados.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = get_settings()

    destination = (
        args.destination
        if args.destination.is_absolute()
        else settings.absolute_path(args.destination)
    )

    cloud_backup_cache = settings.absolute_path(
        Path("artifacts/runtime/cloud_backup_restore")
    )

    backup_file_system = os.getenv(
        "AZURE_BACKUP_FILE_SYSTEM",
        "backup",
    )

    backup_remote_prefix = os.getenv(
        "AZURE_BACKUP_PREFIX",
        "albus-hub/dev",
    )

    cloud_report = download_directory(
        file_system=backup_file_system,
        remote_prefix=backup_remote_prefix,
        local_root=cloud_backup_cache,
    )

    service = RestoreService(
        backup_root=cloud_backup_cache,
        destination=destination,
    )

    report = service.restore_latest()

    report["cloud_source"] = cloud_report

    print(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
        )
    )

    if report["status"] != "success":
        raise SystemExit(
            "Restore terminou com falha de integridade."
        )


if __name__ == "__main__":
    main()
