from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pendulum
from airflow.sdk import dag, task

TRAIN_SCHEDULE = os.getenv(
    "ALBUS_ML_TRAIN_SCHEDULE",
    "0 5 1 * *",
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
    dag_id="albus_hub_ml_training",
    description=("Retreino periódico do modelo de previsão de volume do Albus-Hub."),
    schedule=TRAIN_SCHEDULE,
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
        "training",
    ],
)
def albus_hub_ml_training():
    @task(
        task_id="train_volume_model",
        retries=1,
    )
    def train_volume_model() -> dict:
        return run_project_script("scripts/ml/train_volume_model.py")

    @task(
        task_id="validate_training_publish",
        retries=0,
    )
    def validate_training_publish(
        training_report: dict,
    ) -> dict:
        """Valida a publicação do modelo vigente no ADLS."""

        if training_report.get("status") != "success":
            raise ValueError("O treinamento não terminou com sucesso.")

        stdout = training_report.get(
            "stdout",
            "",
        )

        if "TREINO_ADLS=SUCCESS" not in stdout:
            raise ValueError("O treinamento terminou sem confirmar a publicação do modelo no ADLS.")

        print("Modelo publicado e ponteiro current.json atualizado no ADLS.")

        return {
            "validation": "passed",
            "artifact_store": "ADLS",
            "current_pointer": ("models/volume_forecast/current.json"),
        }

    training = train_volume_model()

    validate_training_publish(training)


albus_hub_ml_training()
