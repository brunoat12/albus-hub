from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pendulum
from airflow.sdk import dag, task


def get_project_root() -> Path:
    """Retorna a raiz do projeto Albus-Hub configurada no ambiente."""
    project_root = os.environ.get("ALBUS_HUB_PROJECT_ROOT")

    if not project_root:
        raise RuntimeError("A variável ALBUS_HUB_PROJECT_ROOT não está configurada.")

    root = Path(project_root).resolve()

    if not root.exists():
        raise RuntimeError(f"Diretório do projeto não encontrado: {root}")

    return root


def run_project_script(
    script: str,
    *args: str,
) -> dict:
    """
    Executa um script do Albus-Hub usando o ambiente Python do próprio projeto.

    O Airflow permanece isolado do ambiente uv do Albus-Hub.
    """
    project_root = get_project_root()

    command = [
        "uv",
        "run",
        "python",
        script,
        *args,
    ]

    result = subprocess.run(
        command,
        cwd=project_root,
        check=True,
        capture_output=True,
        text=True,
    )

    stdout = result.stdout.strip()

    if not stdout:
        return {
            "script": script,
            "status": "success",
            "stdout": "",
        }

    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        return {
            "script": script,
            "status": "success",
            "stdout": stdout,
        }


@dag(
    dag_id="albus_hub_data_protection",
    description=(
        "Pipeline de ingestão, validação, carga analítica e proteção de dados do projeto Albus-Hub."
    ),
    schedule=None,
    start_date=pendulum.datetime(
        2026,
        8,
        9,
        tz="America/Sao_Paulo",
    ),
    catchup=False,
    tags=[
        "albus-hub",
        "fiap",
        "sprint3",
        "data-protection",
    ],
)
def albus_hub_data_protection():

    @task(
        task_id="extract_transform_locaweb",
        retries=1,
    )
    def extract_transform_locaweb() -> dict:
        """Executa ingestão, limpeza e transformação da base Locaweb."""
        return run_project_script("scripts/ingest_locaweb.py")

    @task(
        task_id="validate_silver",
        retries=0,
    )
    def validate_silver(
        ingestion_report: dict,
    ) -> dict:
        """Valida o resultado da ingestão antes da carga Gold."""
        quality_status = ingestion_report.get("quality_status")

        if quality_status == "failed":
            raise ValueError("Quality Gate da camada Silver falhou.")

        if quality_status not in {
            "passed",
            "passed_with_warnings",
        }:
            raise ValueError(f"Status de qualidade inesperado: {quality_status}")

        return {
            "validation": "passed",
            "quality_status": quality_status,
        }

    @task(
        task_id="load_daily_volume_gold",
        retries=1,
    )
    def load_daily_volume_gold(
        silver_validation: dict,
    ) -> dict:
        """Constrói a camada Gold de volume diário."""
        if silver_validation.get("validation") != "passed":
            raise ValueError("Silver não foi validada.")

        return run_project_script("scripts/build_daily_volume_gold.py")

    @task(
        task_id="validate_gold",
        retries=0,
    )
    def validate_gold(
        gold_report: dict,
    ) -> dict:
        """Realiza verificações mínimas sobre a Gold."""
        if os.environ.get("ALBUS_HUB_SIMULATE_FAILURE") == "1":
            raise ValueError("Falha controlada para demonstração de recovery.")
        if not gold_report:
            raise ValueError("O relatório da Gold está vazio.")

        return {
            "validation": "passed",
            "gold_report_received": True,
        }

    @task(
        task_id="backup_data",
        retries=1,
    )
    def backup_data(
        gold_validation: dict,
    ) -> dict:
        """Executa a política automática de backup."""
        if gold_validation.get("validation") != "passed":
            raise ValueError("A Gold não foi validada para backup.")

        report = run_project_script(
            "scripts/run_backup.py",
            "--type",
            "auto",
        )

        if report.get("status") != "success":
            raise ValueError("O backup não terminou com sucesso.")

        return report

    @task(
        task_id="pipeline_complete",
    )
    def pipeline_complete(
        backup_report: dict,
    ) -> None:
        """Marca a conclusão lógica do pipeline."""
        if backup_report.get("status") != "success":
            raise ValueError("O backup não foi concluído.")

        print("Pipeline Albus-Hub concluído com sucesso.")

    ingestion = extract_transform_locaweb()

    silver_ok = validate_silver(ingestion)

    gold = load_daily_volume_gold(silver_ok)

    gold_ok = validate_gold(gold)

    backup_ok = backup_data(gold_ok)

    pipeline_complete(backup_ok)


albus_hub_data_protection()
