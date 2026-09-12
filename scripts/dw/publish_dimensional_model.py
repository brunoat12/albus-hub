from __future__ import annotations

import os
from pathlib import Path

from albus_hub.storage.adls import upload_file

STORAGE_ACCOUNT_ENV = "AZURE_STORAGE_ACCOUNT_NAME"

FILE_SYSTEM = "gold"
REMOTE_DIR = "dw"
LOCAL_DIR = Path("data/dw")

DW_FILES = [
    "dim_tempo.parquet",
    "dim_prioridade.parquet",
    "dim_produto.parquet",
    "dim_categoria.parquet",
    "dim_grupo.parquet",
    "dim_item_configuracao.parquet",
    "fato_incidente.parquet",
]


def main() -> None:
    if not os.getenv(STORAGE_ACCOUNT_ENV):
        raise RuntimeError(f"{STORAGE_ACCOUNT_ENV} não está configurada.")

    print("=== PUBLICAÇÃO DO DW NO ADLS ===")

    missing_files = [filename for filename in DW_FILES if not (LOCAL_DIR / filename).exists()]

    if missing_files:
        raise FileNotFoundError("Arquivos dimensionais ausentes: " + ", ".join(missing_files))

    for filename in DW_FILES:
        local_path = LOCAL_DIR / filename
        remote_path = f"{REMOTE_DIR}/{filename}"

        print(f"Enviando {local_path} -> {FILE_SYSTEM}/{remote_path}")

        upload_file(
            local_path=local_path,
            file_system=FILE_SYSTEM,
            remote_path=remote_path,
        )

    print()
    print("DW_ADLS_PUBLISH=SUCCESS")


if __name__ == "__main__":
    main()
