from __future__ import annotations

import os
from pathlib import Path

from albus_hub.storage.adls import upload_file

STORAGE_ACCOUNT_ENV = "AZURE_STORAGE_ACCOUNT_NAME"

FILE_SYSTEM = "gold"
LOCAL_DIR = Path("data/gold")
REMOTE_DIR = "analytics"

GOLD_FILES = [
    "daily_incident_volume.parquet",
    "daily_incident_breakdown.parquet",
]


def main() -> None:
    if not os.getenv(STORAGE_ACCOUNT_ENV):
        raise RuntimeError(
            f"{STORAGE_ACCOUNT_ENV} não está configurada."
        )

    print("=== PUBLICAÇÃO GOLD ANALÍTICO ===")

    for filename in GOLD_FILES:
        local_path = LOCAL_DIR / filename

        if not local_path.exists():
            raise FileNotFoundError(
                f"Gold não encontrado: {local_path}"
            )

        remote_path = f"{REMOTE_DIR}/{filename}"

        print(
            f"Enviando {local_path} "
            f"-> {FILE_SYSTEM}/{remote_path}"
        )

        upload_file(
            local_path=local_path,
            file_system=FILE_SYSTEM,
            remote_path=remote_path,
        )

    print()
    print("ANALYTICS_GOLD_PUBLISH=SUCCESS")


if __name__ == "__main__":
    main()