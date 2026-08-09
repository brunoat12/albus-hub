from __future__ import annotations

import argparse
import json
from pathlib import Path

from albus_hub.config import get_settings
from albus_hub.storage import RestoreService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Restaura o backup mais recente do Albus-Hub.")

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

    service = RestoreService(
        backup_root=settings.absolute_path(settings.data_backup_path),
        destination=destination,
    )

    report = service.restore_latest()

    print(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
        )
    )

    if report["status"] != "success":
        raise SystemExit("Restore terminou com falha de integridade.")


if __name__ == "__main__":
    main()
