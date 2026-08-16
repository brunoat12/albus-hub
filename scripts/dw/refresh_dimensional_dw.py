from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

import pandas as pd
from sqlalchemy import text

from albus_hub.config.settings import get_settings
from albus_hub.storage.mysql import create_mysql_engine

RESOURCE_GROUP = os.getenv(
    "AZURE_RESOURCE_GROUP",
    "rg-albus-hub-dev",
)

DATA_FACTORY = os.getenv(
    "AZURE_DATA_FACTORY_NAME",
    "adf-albushub-fiap2026-dev",
)

PIPELINE_NAME = os.getenv(
    "ALBUS_DW_ADF_PIPELINE",
    "PL_LOAD_DIMENSIONAL_DW",
)

POLL_INTERVAL_SECONDS = 15

TIMEOUT_SECONDS = int(
    os.getenv(
        "ALBUS_DW_ADF_TIMEOUT_SECONDS",
        "1800",
    )
)

DW_DIR = Path("data/dw")

DW_FILES = {
    "dim_tempo": "dim_tempo.parquet",
    "dim_prioridade": "dim_prioridade.parquet",
    "dim_produto": "dim_produto.parquet",
    "dim_categoria": "dim_categoria.parquet",
    "dim_grupo": "dim_grupo.parquet",
    "dim_item_configuracao": (
        "dim_item_configuracao.parquet"
    ),
    "fato_incidente": "fato_incidente.parquet",
}

DIMENSION_TABLES = [
    "dim_tempo",
    "dim_prioridade",
    "dim_produto",
    "dim_categoria",
    "dim_grupo",
    "dim_item_configuracao",
]


def expected_counts() -> dict[str, int]:
    """Obtém as contagens esperadas dos Parquets publicados."""

    counts: dict[str, int] = {}

    for table, filename in DW_FILES.items():
        path = DW_DIR / filename

        if not path.exists():
            raise FileNotFoundError(
                f"Arquivo dimensional não encontrado: {path}"
            )

        count = len(
            pd.read_parquet(
                path,
                columns=None,
            )
        )

        if count <= 0:
            raise ValueError(
                f"Arquivo dimensional vazio: {path}"
            )

        counts[table] = count

    return counts


def clear_mysql_dw() -> None:
    """Limpa o DW respeitando as foreign keys."""

    engine = create_mysql_engine(
        get_settings()
    )

    with engine.begin() as connection:
        print(
            "Removendo registros da FATO..."
        )

        connection.execute(
            text(
                "DELETE FROM fato_incidente"
            )
        )

        for table in DIMENSION_TABLES:
            print(
                f"Removendo registros de {table}..."
            )

            connection.execute(
                text(
                    f"DELETE FROM {table}"
                )
            )


def run_command(
    command: list[str],
) -> str:
    """Executa comando externo e retorna stdout."""

    result = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
    )

    return result.stdout.strip()


def trigger_adf_pipeline() -> str:
    """Dispara o pipeline dimensional no ADF."""

    run_id = run_command(
        [
            "az",
            "datafactory",
            "pipeline",
            "create-run",
            "--resource-group",
            RESOURCE_GROUP,
            "--factory-name",
            DATA_FACTORY,
            "--name",
            PIPELINE_NAME,
            "--query",
            "runId",
            "-o",
            "tsv",
        ]
    )

    if not run_id:
        raise RuntimeError(
            "O ADF não retornou run_id."
        )

    print(
        f"ADF_RUN_ID={run_id}"
    )

    return run_id


def get_adf_status(
    run_id: str,
) -> str:
    """Consulta o estado atual da execução do ADF."""

    return run_command(
        [
            "az",
            "datafactory",
            "pipeline-run",
            "show",
            "--resource-group",
            RESOURCE_GROUP,
            "--factory-name",
            DATA_FACTORY,
            "--run-id",
            run_id,
            "--query",
            "status",
            "-o",
            "tsv",
        ]
    )


def wait_for_adf(
    run_id: str,
) -> None:
    """Espera o término do pipeline dimensional."""

    started_at = time.monotonic()

    terminal_statuses = {
        "Succeeded",
        "Failed",
        "Cancelled",
    }

    while True:
        status = get_adf_status(
            run_id
        )

        print(
            f"ADF_STATUS={status}"
        )

        if status in terminal_statuses:
            break

        elapsed = (
            time.monotonic()
            - started_at
        )

        if elapsed >= TIMEOUT_SECONDS:
            raise TimeoutError(
                "Tempo máximo aguardando "
                "o ADF foi excedido."
            )

        time.sleep(
            POLL_INTERVAL_SECONDS
        )

    if status != "Succeeded":
        raise RuntimeError(
            "Pipeline ADF terminou com "
            f"status {status}."
        )


def validate_mysql_dw(
    expected: dict[str, int],
) -> None:
    """Valida counts e integridade referencial após a carga."""

    engine = create_mysql_engine(
        get_settings()
    )

    with engine.connect() as connection:
        print()
        print(
            "=== VALIDAÇÃO DE CONTAGENS ==="
        )

        for table, expected_count in expected.items():
            actual_count = connection.execute(
                text(
                    f"SELECT COUNT(*) "
                    f"FROM {table}"
                )
            ).scalar_one()

            print(
                f"{table}: "
                f"esperado={expected_count} "
                f"mysql={actual_count}"
            )

            if actual_count != expected_count:
                raise ValueError(
                    f"Contagem divergente em {table}: "
                    f"esperado={expected_count}, "
                    f"mysql={actual_count}"
                )

        orphan_checks = {
            "tempo": """
                SELECT COUNT(*)
                FROM fato_incidente f
                LEFT JOIN dim_tempo d
                    ON f.sk_tempo = d.sk_tempo
                WHERE d.sk_tempo IS NULL
            """,
            "prioridade": """
                SELECT COUNT(*)
                FROM fato_incidente f
                LEFT JOIN dim_prioridade d
                    ON f.sk_prioridade = d.sk_prioridade
                WHERE d.sk_prioridade IS NULL
            """,
            "produto": """
                SELECT COUNT(*)
                FROM fato_incidente f
                LEFT JOIN dim_produto d
                    ON f.sk_produto = d.sk_produto
                WHERE d.sk_produto IS NULL
            """,
            "categoria": """
                SELECT COUNT(*)
                FROM fato_incidente f
                LEFT JOIN dim_categoria d
                    ON f.sk_categoria = d.sk_categoria
                WHERE d.sk_categoria IS NULL
            """,
            "grupo": """
                SELECT COUNT(*)
                FROM fato_incidente f
                LEFT JOIN dim_grupo d
                    ON f.sk_grupo = d.sk_grupo
                WHERE d.sk_grupo IS NULL
            """,
            "item_configuracao": """
                SELECT COUNT(*)
                FROM fato_incidente f
                LEFT JOIN dim_item_configuracao d
                    ON f.sk_item_configuracao =
                       d.sk_item_configuracao
                WHERE d.sk_item_configuracao IS NULL
            """,
        }

        print()
        print(
            "=== VALIDAÇÃO DE FKs ==="
        )

        for dimension, query in orphan_checks.items():
            orphan_count = connection.execute(
                text(query)
            ).scalar_one()

            print(
                f"{dimension}: "
                f"orfãos={orphan_count}"
            )

            if orphan_count != 0:
                raise ValueError(
                    "Integridade referencial inválida "
                    f"para {dimension}: "
                    f"{orphan_count} órfãos."
                )


def main() -> None:
    print(
        "=== REFRESH DIMENSIONAL DW ==="
    )

    expected = expected_counts()

    print()
    print(
        "Contagens esperadas:"
    )

    for table, count in expected.items():
        print(
            f"{table}: {count}"
        )

    print()
    print(
        "Limpando DW atual no MySQL..."
    )

    clear_mysql_dw()

    print()
    print(
        "Disparando pipeline ADF..."
    )

    run_id = trigger_adf_pipeline()

    wait_for_adf(
        run_id
    )

    validate_mysql_dw(
        expected
    )

    print()
    print(
        "DW_REFRESH=SUCCESS"
    )


if __name__ == "__main__":
    main()