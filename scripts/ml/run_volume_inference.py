from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from albus_hub.config.settings import (
    get_settings,
)
from albus_hub.integration.volume_predictions import (
    validate_volume_predictions,
)
from albus_hub.ml.volume_forecast_v32 import (
    load_volume_bundle,
    predict_volume,
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

TRUSTED_FILE_SYSTEM = "trusted"
GOLD_FILE_SYSTEM = "gold"
MODELS_FILE_SYSTEM = "models"

TRUSTED_REMOTE_PATH = "ml/locaweb_incidents.parquet"

CURRENT_REMOTE_PATH = "volume_forecast/current.json"

RUNTIME_DIR = Path("artifacts/runtime/ml_inference_v32")

LOCAL_SOURCE_PATH = RUNTIME_DIR / "locaweb_incidents.parquet"

LOCAL_CURRENT_PATH = RUNTIME_DIR / "current.json"

LOCAL_BUNDLE_PATH = RUNTIME_DIR / "current_bundle.joblib"

LOCAL_OUTPUT_PATH = RUNTIME_DIR / "volume_predictions.parquet"

LOCAL_STREAMLIT_OUTPUT = Path("data/gold/volume_predictions.parquet")


def main() -> None:
    if not os.getenv(STORAGE_ACCOUNT_ENV):
        raise RuntimeError(f"{STORAGE_ACCOUNT_ENV} não está configurada.")

    RUNTIME_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    print("=== INFERENCIA DIARIA ML V3.2 ===")

    print()
    print("Baixando Silver governada do ADLS...")

    download_file(
        file_system=(TRUSTED_FILE_SYSTEM),
        remote_path=(TRUSTED_REMOTE_PATH),
        local_path=(LOCAL_SOURCE_PATH),
    )

    print("Baixando ponteiro do modelo vigente...")

    download_file(
        file_system=(MODELS_FILE_SYSTEM),
        remote_path=(CURRENT_REMOTE_PATH),
        local_path=(LOCAL_CURRENT_PATH),
    )

    current = json.loads(LOCAL_CURRENT_PATH.read_text(encoding="utf-8"))

    model_version = current.get("model_version")

    bundle_remote_path = current.get("bundle_path")

    if not model_version:
        raise ValueError("current.json sem model_version.")

    if not bundle_remote_path:
        raise ValueError("current.json ainda não possui bundle_path v3.2.")

    print(
        "Modelo vigente:",
        model_version,
    )

    print(
        "Bundle:",
        bundle_remote_path,
    )

    print()
    print("Baixando bundle vigente...")

    download_file(
        file_system=(MODELS_FILE_SYSTEM),
        remote_path=(bundle_remote_path),
        local_path=(LOCAL_BUNDLE_PATH),
    )

    source = pd.read_parquet(LOCAL_SOURCE_PATH)

    bundle = load_volume_bundle(LOCAL_BUNDLE_PATH)

    bundle_version = str(bundle.get("model_version"))

    if bundle_version != str(model_version):
        raise RuntimeError(
            f"Versão do bundle difere do current.json: {bundle_version} != {model_version}"
        )

    generated_at = datetime.now(UTC)

    frame = predict_volume(
        source,
        bundle,
        generated_at=generated_at,
    )

    frame = validate_volume_predictions(frame)

    if len(frame) != 12:
        raise RuntimeError("A inferência v3.2 deve gerar exatamente 12 previsões.")

    print()
    print("===== PREVISOES =====")

    for row in frame.itertuples(index=False):
        reference_date = pd.Timestamp(row.reference_date).date()

        print(
            f"{row.priority_scope} "
            f"{row.horizon}: "
            f"{reference_date} "
            f"-> "
            f"{row.predicted_incident_count:.2f} "
            f"[{row.lower_bound:.2f}, "
            f"{row.upper_bound:.2f}] "
            f"| {row.model_name}"
        )

    frame.to_parquet(
        LOCAL_OUTPUT_PATH,
        index=False,
    )

    run_date = generated_at.strftime("%Y-%m-%d")

    run_id = generated_at.strftime("%Y%m%dT%H%M%SZ")

    remote_prediction_path = (
        f"ml/volume_predictions/run_date={run_date}/run_id={run_id}/volume_predictions.parquet"
    )

    print()
    print("Publicando previsão no ADLS...")

    upload_file(
        local_path=(LOCAL_OUTPUT_PATH),
        file_system=(GOLD_FILE_SYSTEM),
        remote_path=(remote_prediction_path),
    )

    print()
    print("Persistindo previsão vigente no MySQL...")

    settings = get_settings()

    repository = MySQLRepository(create_mysql_engine(settings))

    repository.ensure_ml_volume_predictions_table()

    mysql_rows = []

    for row in frame.to_dict(orient="records"):
        mysql_rows.append(
            {
                "priority_scope": str(row["priority_scope"]),
                "horizon": str(row["horizon"]),
                "reference_date": pd.Timestamp(row["reference_date"]).to_pydatetime(),
                "predicted_incident_count": float(row["predicted_incident_count"]),
                "lower_bound": float(row["lower_bound"]),
                "upper_bound": float(row["upper_bound"]),
                "model_name": str(row["model_name"]),
                "generated_at": pd.Timestamp(row["generated_at"]).to_pydatetime(),
                "model_version": str(row["model_version"]),
            }
        )

    repository.upsert_ml_volume_predictions(mysql_rows)

    print("MYSQL_PREDICTIONS_UPSERT=SUCCESS")

    LOCAL_STREAMLIT_OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    LOCAL_STREAMLIT_OUTPUT.write_bytes(LOCAL_OUTPUT_PATH.read_bytes())

    print()
    print("INFERENCE_ADLS=SUCCESS")
    print(
        "Modelo utilizado:",
        model_version,
    )
    print(
        "Previsões geradas:",
        len(frame),
    )
    print(
        "Previsão:",
        f"{GOLD_FILE_SYSTEM}/{remote_prediction_path}",
    )


if __name__ == "__main__":
    main()
