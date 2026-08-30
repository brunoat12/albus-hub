from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pendulum
from airflow.sdk import dag, task

TRAIN_SCHEDULE = os.getenv(
    "ALBUS_DL_TRAIN_SCHEDULE",
    "30 5 1 * *",
)


def get_project_root() -> Path:
    project_root = os.environ.get(
        "ALBUS_HUB_PROJECT_ROOT"
    )

    if not project_root:
        raise RuntimeError(
            "A variável ALBUS_HUB_PROJECT_ROOT "
            "não está configurada."
        )

    root = Path(project_root).resolve()

    if not root.exists():
        raise RuntimeError(
            f"Diretório do projeto não encontrado: {root}"
        )

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
    dag_id="albus_hub_dl_training",
    description=(
        "Retreino periódico do modelo ANN "
        "de score de risco do Albus-Hub."
    ),
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
        "sprint4",
        "deep-learning",
        "risk-score",
        "training",
    ],
)
def albus_hub_dl_training():
    @task(
        task_id="validate_environment",
        retries=0,
    )
    def validate_environment() -> dict:
        required_variables = [
            "AZURE_STORAGE_ACCOUNT_NAME",
        ]

        missing = [
            variable
            for variable in required_variables
            if not os.environ.get(variable)
        ]

        if missing:
            raise RuntimeError(
                "Variáveis obrigatórias ausentes: "
                + ", ".join(missing)
            )

        return {
            "validation": "passed",
        }

    @task(
        task_id="train_risk_model",
        retries=1,
    )
    def train_risk_model(
        validation: dict,
    ) -> dict:
        if (
            validation.get("validation")
            != "passed"
        ):
            raise ValueError(
                "Validação de ambiente falhou."
            )

        return run_project_script(
            "scripts/train_risk_model.py"
        )

    @task(
        task_id="validate_training_publish",
        retries=0,
    )
    def validate_training_publish(
        training_report: dict,
    ) -> dict:
        if (
            training_report.get("status")
            != "success"
        ):
            raise ValueError(
                "O treinamento DL não terminou "
                "com sucesso."
            )

        stdout = training_report.get(
            "stdout",
            "",
        )

        if (
            "DL_TREINO_ADLS=SUCCESS"
            not in stdout
        ):
            raise ValueError(
                "Treinamento DL terminou sem "
                "confirmar publicação no ADLS."
            )

        print(
            "Modelo DL publicado e "
            "risk/current.json atualizado."
        )

        return {
            "validation": "passed",
            "artifact_store": "ADLS",
            "current_pointer": (
                "models/risk/current.json"
            ),
        }

    validation = validate_environment()

    training = train_risk_model(
        validation
    )

    validate_training_publish(
        training
    )


albus_hub_dl_training()
