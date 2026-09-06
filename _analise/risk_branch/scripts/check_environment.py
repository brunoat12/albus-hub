from __future__ import annotations

import sys

import duckdb
import numpy as np
import pandas as pd
import pyarrow
import streamlit

from albus_hub.config import PROJECT_ROOT, get_settings


def main() -> None:
    """Verifica a instalação básica do ambiente do Albus-Hub."""
    settings = get_settings()
    settings.create_local_directories()

    print("=== Albus-Hub: verificação do ambiente ===")
    print(f"Raiz do projeto: {PROJECT_ROOT}")
    print(f"Ambiente: {settings.app_env}")
    print(f"Cloud provider: {settings.cloud_provider}")
    print()
    print(f"Python: {sys.version.split()[0]}")
    print(f"Pandas: {pd.__version__}")
    print(f"NumPy: {np.__version__}")
    print(f"PyArrow: {pyarrow.__version__}")
    print(f"DuckDB: {duckdb.__version__}")
    print(f"Streamlit: {streamlit.__version__}")

    result = duckdb.sql("SELECT 20 + 6 AS resultado").fetchone()

    if result is None or result[0] != 26:
        raise RuntimeError("O teste do DuckDB falhou.")

    print()
    print("[OK] Importações realizadas")
    print("[OK] Configurações carregadas")
    print("[OK] Pastas locais verificadas")
    print("[OK] DuckDB executou uma consulta")
    print("=== Ambiente básico configurado com sucesso ===")


if __name__ == "__main__":
    main()
