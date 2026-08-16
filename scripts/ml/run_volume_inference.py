from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from albus_hub.config.settings import get_settings
from albus_hub.integration.volume_predictions import (
    validate_volume_predictions,
)
from albus_hub.ml.volume_forecast import (
    PRIORITY_SCOPES,
    forecast,
    load_model,
    prepare_scope,
)
from albus_hub.storage.adls import (
    download_file,
    upload_file,
)
from albus_hub.storage.mysql import (
    MySQLRepository,
    create_mysql_engine,
)

STORAGE_ACCOUNT_ENV = "AZURE_STORAGE_ACCOUNT_NAME"

GOLD_FILE_SYSTEM = "gold"
MODELS_FILE_SYSTEM = "models"

GOLD_REMOTE_PATH = (
    "analytics/daily_incident_volume.parquet"
)

CURRENT_REMOTE_PATH = (
    "volume_forecast/current.json"
)

RUNTIME_DIR = Path(
    "artifacts/runtime/ml_inference"
)

LOCAL_GOLD_PATH = (
    RUNTIME_DIR
    / "daily_incident_volume.parquet"
)

LOCAL_CURRENT_PATH = (
    RUNTIME_DIR
    / "current.json"
)

LOCAL_MODEL_PATH = (
    RUNTIME_DIR
    / "current_model.npz"
)

LOCAL_OUTPUT_PATH = (
    RUNTIME_DIR
    / "volume_predictions.parquet"
)

# Mantido temporariamente para compatibilidade local
# com o Streamlit durante a transição.
LOCAL_STREAMLIT_OUTPUT = Path(
    "data/gold/volume_predictions.parquet"
)


def main() -> None:
    if not os.getenv(STORAGE_ACCOUNT_ENV):
        raise RuntimeError(
            f"{STORAGE_ACCOUNT_ENV} não está configurada."
        )

    RUNTIME_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    print("=== INFERENCIA DIARIA DE VOLUME ===")

    print()
    print("Baixando Gold do ADLS...")

    download_file(
        file_system=GOLD_FILE_SYSTEM,
        remote_path=GOLD_REMOTE_PATH,
        local_path=LOCAL_GOLD_PATH,
    )

    print("Baixando ponteiro do modelo vigente...")

    download_file(
        file_system=MODELS_FILE_SYSTEM,
        remote_path=CURRENT_REMOTE_PATH,
        local_path=LOCAL_CURRENT_PATH,
    )

    current = json.loads(
        LOCAL_CURRENT_PATH.read_text(
            encoding="utf-8"
        )
    )

    model_version = current.get(
        "model_version"
    )

    model_remote_path = current.get(
        "model_path"
    )

    if not model_version:
        raise ValueError(
            "current.json não possui model_version."
        )

    if not model_remote_path:
        raise ValueError(
            "current.json não possui model_path."
        )

    print(
        "Modelo vigente:",
        model_version,
    )

    print(
        "Artefato:",
        model_remote_path,
    )

    print()
    print("Baixando modelo vigente do ADLS...")

    download_file(
        file_system=MODELS_FILE_SYSTEM,
        remote_path=model_remote_path,
        local_path=LOCAL_MODEL_PATH,
    )

    source = pd.read_parquet(
        LOCAL_GOLD_PATH
    )

    models = load_model(
        LOCAL_MODEL_PATH
    )

    generated_at = datetime.now(UTC)

    rows = []

    for scope in PRIORITY_SCOPES:
        scoped = prepare_scope(
            source,
            scope,
        )

        predictions = forecast(
            scoped,
            models[scope],
        )

        for step, horizon in (
            (1, "D+1"),
            (7, "D+7"),
        ):
            reference_date, value = (
                predictions[step]
            )

            rows.append(
                {
                    "reference_date": reference_date,
                    "generated_at": generated_at.replace(
                        tzinfo=None
                    ),
                    "horizon": horizon,
                    "priority_scope": scope,
                    "predicted_incident_count": round(
                        value,
                        2,
                    ),
                    "model_version": model_version,
                }
            )

            print(
                f"{scope} {horizon}: "
                f"{reference_date.date()} "
                f"-> {value:.2f}"
            )

    frame = pd.DataFrame(
        rows
    )

    frame = validate_volume_predictions(
        frame
    )

    frame.to_parquet(
        LOCAL_OUTPUT_PATH,
        index=False,
    )

    run_date = generated_at.strftime(
        "%Y-%m-%d"
    )

    run_id = generated_at.strftime(
        "%Y%m%dT%H%M%SZ"
    )

    remote_prediction_path = (
        "ml/volume_predictions/"
        f"run_date={run_date}/"
        f"run_id={run_id}/"
        "volume_predictions.parquet"
    )

    print()
    print("Publicando previsão no ADLS...")

    upload_file(
        local_path=LOCAL_OUTPUT_PATH,
        file_system=GOLD_FILE_SYSTEM,
        remote_path=remote_prediction_path,
    )

    print()
    print("Persistindo previsão vigente no MySQL...")

    settings = get_settings()

    repository = MySQLRepository(
        create_mysql_engine(
            settings
        )
    )

    repository.ensure_ml_volume_predictions_table()

    mysql_rows = []

    for row in frame.to_dict(
        orient="records"
    ):
        mysql_rows.append(
            {
                "priority_scope": str(
                    row["priority_scope"]
                ),
                "horizon": str(
                    row["horizon"]
                ),
                "reference_date": pd.Timestamp(
                    row["reference_date"]
                ).to_pydatetime(),
                "predicted_incident_count": float(
                    row[
                        "predicted_incident_count"
                    ]
                ),
                "generated_at": pd.Timestamp(
                    row["generated_at"]
                ).to_pydatetime(),
                "model_version": str(
                    row["model_version"]
                ),
            }
        )

    repository.upsert_ml_volume_predictions(
        mysql_rows
    )

    print(
        "MYSQL_PREDICTIONS_UPSERT=SUCCESS"
    )

    # Compatibilidade temporária com o Streamlit local.
    LOCAL_STREAMLIT_OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    LOCAL_STREAMLIT_OUTPUT.write_bytes(
        LOCAL_OUTPUT_PATH.read_bytes()
    )

    print()
    print("INFERENCE_ADLS=SUCCESS")

    print(
        "Modelo utilizado:",
        model_version,
    )

    print(
        "Previsão:",
        f"{GOLD_FILE_SYSTEM}/{remote_prediction_path}",
    )


if __name__ == "__main__":
    main()