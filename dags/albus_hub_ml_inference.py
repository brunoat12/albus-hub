from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pendulum
from airflow.sdk import dag, task

INFERENCE_SCHEDULE = os.getenv(
    "ALBUS_ML_INFERENCE_SCHEDULE",
    "0 6 * * *",
)


def get_project_root() -> Path:
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

    if stdout:
        print(stdout)

    return {
        "script": script,
        "status": "success",
        "stdout": stdout,
    }


@dag(
    dag_id="albus_hub_ml_inference",
    description=("Inferência diária D+1 e D+7 usando o modelo vigente do Albus-Hub."),
    schedule=INFERENCE_SCHEDULE,
    start_date=pendulum.datetime(
        2026,
        8,
        1,
        tz="America/Sao_Paulo",
    ),
    catchup=False,
    max_active_runs=1,
    tags=[
        "albus-hub",
        "fiap",
        "sprint3",
        "machine-learning",
        "inference",
    ],
)
def albus_hub_ml_inference():
    @task(
        task_id="validate_environment",
        retries=0,
    )
    def validate_environment() -> dict:
        """Valida configurações necessárias para a inferência."""

        required_variables = [
            "AZURE_STORAGE_ACCOUNT_NAME",
            "MYSQL_HOST",
            "MYSQL_USER",
            "MYSQL_PASSWORD",
            "MYSQL_DB",
        ]

        missing = [variable for variable in required_variables if not os.environ.get(variable)]

        if missing:
            raise RuntimeError("Variáveis obrigatórias ausentes: " + ", ".join(missing))

        return {
            "validation": "passed",
        }

    @task(
        task_id="run_daily_inference",
        retries=1,
    )
    def run_daily_inference(
        validation: dict,
    ) -> dict:
        if validation.get("validation") != "passed":
            raise ValueError("Validação de entrada falhou.")

        return run_project_script("scripts/ml/run_volume_inference.py")

    @task(
        task_id="validate_predictions",
        retries=0,
    )
    def validate_predictions(
        inference_report: dict,
    ) -> None:
        """Valida a publicação da inferência no ADLS e MySQL."""

        if inference_report.get("status") != "success":
            raise ValueError("Inferência não terminou com sucesso.")

        stdout = inference_report.get(
            "stdout",
            "",
        )

        required_markers = [
            "INFERENCE_ADLS=SUCCESS",
            "MYSQL_PREDICTIONS_UPSERT=SUCCESS",
        ]

        missing_markers = [marker for marker in required_markers if marker not in stdout]

        if missing_markers:
            raise ValueError("Inferência terminou sem confirmar: " + ", ".join(missing_markers))

        print("Inferência publicada com sucesso no ADLS e no MySQL.")

    validation = validate_environment()

    inference = run_daily_inference(validation)

    validate_predictions(inference)


albus_hub_ml_inference()
