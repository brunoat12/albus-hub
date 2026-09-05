from __future__ import annotations

import json
import os
import runpy
import shutil
from datetime import UTC, datetime
from pathlib import Path

import joblib

from albus_hub.storage.adls import (
    download_file,
    upload_file,
)

STORAGE_ACCOUNT_ENV = "AZURE_STORAGE_ACCOUNT_NAME"

TRUSTED_FILE_SYSTEM = "trusted"
MODELS_FILE_SYSTEM = "models"

TRUSTED_REMOTE_PATH = "ml/locaweb_incidents.parquet"

CURRENT_REMOTE_PATH = "volume_forecast/current.json"

RUNTIME_DIR = Path("artifacts/runtime/ml_training_v32")

LOCAL_SOURCE_PATH = RUNTIME_DIR / "locaweb_incidents.parquet"

LOCAL_BUNDLE_PATH = RUNTIME_DIR / "model_bundle.joblib"

LOCAL_METADATA_PATH = RUNTIME_DIR / "metadata.json"

LOCAL_METRICS_PATH = RUNTIME_DIR / "metrics.json"

LOCAL_CURRENT_PATH = RUNTIME_DIR / "current.json"

CANONICAL_METRICS_PATH = Path("ml_volume/outputs/metrics.json")

EXPORTER_PATH = Path("scripts/ml/export_volume_v32_bundle.py")

LOCAL_CACHE_DIR = Path("artifacts/models/volume_forecast")


def main() -> None:
    if not os.getenv(STORAGE_ACCOUNT_ENV):
        raise RuntimeError(f"{STORAGE_ACCOUNT_ENV} não está configurada.")

    RUNTIME_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    print("=== TREINO ML V3.2 DE VOLUME ===")

    print(
        "Fonte oficial:",
        f"{TRUSTED_FILE_SYSTEM}/{TRUSTED_REMOTE_PATH}",
    )

    print()
    print("Baixando Silver governada do ADLS...")

    download_file(
        file_system=(TRUSTED_FILE_SYSTEM),
        remote_path=(TRUSTED_REMOTE_PATH),
        local_path=(LOCAL_SOURCE_PATH),
    )

    os.environ["ALBUS_ML_SILVER_PATH"] = str(LOCAL_SOURCE_PATH.resolve())

    print()
    print("Executando seleção e treino canônico v3.2...")

    runpy.run_path(
        str(EXPORTER_PATH),
        run_name="__main__",
    )

    if not LOCAL_BUNDLE_PATH.exists():
        raise RuntimeError("O treinamento não gerou model_bundle.joblib.")

    if not LOCAL_METADATA_PATH.exists():
        raise RuntimeError("O treinamento não gerou metadata.json.")

    if not CANONICAL_METRICS_PATH.exists():
        raise RuntimeError("O treinamento não gerou metrics.json.")

    shutil.copy2(
        CANONICAL_METRICS_PATH,
        LOCAL_METRICS_PATH,
    )

    source_label = f"{TRUSTED_FILE_SYSTEM}/{TRUSTED_REMOTE_PATH}"

    bundle = joblib.load(LOCAL_BUNDLE_PATH)

    bundle["source"] = source_label

    joblib.dump(
        bundle,
        LOCAL_BUNDLE_PATH,
    )

    metadata = json.loads(LOCAL_METADATA_PATH.read_text(encoding="utf-8"))

    metadata["training_source"] = source_label

    LOCAL_METADATA_PATH.write_text(
        json.dumps(
            metadata,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    model_version = str(metadata["model_version"])

    training_end_date = str(metadata["training_end_date"])

    trained_at = str(metadata["trained_at"])

    run_timestamp = datetime.now(UTC)

    run_id = run_timestamp.strftime("%Y%m%dT%H%M%SZ")

    remote_base = f"volume_forecast/{model_version}/{run_id}"

    remote_bundle_path = f"{remote_base}/model_bundle.joblib"

    remote_metadata_path = f"{remote_base}/metadata.json"

    remote_metrics_path = f"{remote_base}/metrics.json"

    print()
    print("Publicando bundle versionado no ADLS...")

    upload_file(
        local_path=(LOCAL_BUNDLE_PATH),
        file_system=(MODELS_FILE_SYSTEM),
        remote_path=(remote_bundle_path),
    )

    upload_file(
        local_path=(LOCAL_METADATA_PATH),
        file_system=(MODELS_FILE_SYSTEM),
        remote_path=(remote_metadata_path),
    )

    upload_file(
        local_path=(LOCAL_METRICS_PATH),
        file_system=(MODELS_FILE_SYSTEM),
        remote_path=(remote_metrics_path),
    )

    current = {
        "model_version": model_version,
        "artifact_format": "joblib",
        "trained_at": trained_at,
        "training_end_date": training_end_date,
        "training_source": source_label,
        "bundle_path": remote_bundle_path,
        "metadata_path": remote_metadata_path,
        "metrics_path": remote_metrics_path,
    }

    LOCAL_CURRENT_PATH.write_text(
        json.dumps(
            current,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    # Atualizado por último:
    # nunca apontamos current.json
    # para artefato incompleto.
    upload_file(
        local_path=(LOCAL_CURRENT_PATH),
        file_system=(MODELS_FILE_SYSTEM),
        remote_path=(CURRENT_REMOTE_PATH),
    )

    LOCAL_CACHE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    shutil.copy2(
        LOCAL_BUNDLE_PATH,
        LOCAL_CACHE_DIR / "current.joblib",
    )

    shutil.copy2(
        LOCAL_METADATA_PATH,
        LOCAL_CACHE_DIR / "metadata.json",
    )

    shutil.copy2(
        LOCAL_METRICS_PATH,
        LOCAL_CACHE_DIR / "metrics.json",
    )

    print()
    print("TREINO_ADLS=SUCCESS")
    print(
        "Modelo:",
        model_version,
    )
    print(
        "Bundle:",
        f"{MODELS_FILE_SYSTEM}/{remote_bundle_path}",
    )
    print(
        "Componentes:",
        metadata["component_count"],
    )
    print(
        "Current:",
        f"models/{CURRENT_REMOTE_PATH}",
    )


if __name__ == "__main__":
    main()
