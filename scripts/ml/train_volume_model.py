from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from albus_hub.ml.volume_forecast import (
    MODEL_VERSION,
    PRIORITY_SCOPES,
    build_training_features,
    evaluate_model,
    fit_model,
    prepare_scope,
    save_model,
)
from albus_hub.storage.adls import (
    download_file,
    upload_file,
)

STORAGE_ACCOUNT_ENV = "AZURE_STORAGE_ACCOUNT_NAME"

GOLD_FILE_SYSTEM = "gold"
MODELS_FILE_SYSTEM = "models"

GOLD_REMOTE_PATH = (
    "analytics/daily_incident_volume.parquet"
)

RUNTIME_DIR = Path(
    "artifacts/runtime/ml_training"
)

LOCAL_GOLD_PATH = (
    RUNTIME_DIR
    / "daily_incident_volume.parquet"
)

LOCAL_MODEL_PATH = (
    RUNTIME_DIR
    / "model.npz"
)

LOCAL_METADATA_PATH = (
    RUNTIME_DIR
    / "metadata.json"
)

LOCAL_CURRENT_PATH = (
    RUNTIME_DIR
    / "current.json"
)

# Mantido como cache local para desenvolvimento/testes.
LOCAL_CACHE_DIR = Path(
    "artifacts/models/volume_forecast"
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

    print("=== TREINO DO MODELO DE VOLUME ===")
    print(
        "Fonte oficial:",
        f"ADLS/{GOLD_FILE_SYSTEM}/{GOLD_REMOTE_PATH}",
    )

    print()
    print("Baixando Gold do ADLS...")

    download_file(
        file_system=GOLD_FILE_SYSTEM,
        remote_path=GOLD_REMOTE_PATH,
        local_path=LOCAL_GOLD_PATH,
    )

    source = pd.read_parquet(
        LOCAL_GOLD_PATH
    )

    coefficients = {}
    metrics = {}

    for scope in PRIORITY_SCOPES:
        scoped = prepare_scope(
            source,
            scope,
        )

        features = build_training_features(
            scoped
        )

        metrics[scope] = evaluate_model(
            features
        )

        coefficients[scope] = fit_model(
            features
        )

        print(
            f"{scope}: "
            f"MAE={metrics[scope]['mae']:.2f} | "
            f"RMSE={metrics[scope]['rmse']:.2f}"
        )

    trained_at = datetime.now(UTC)

    run_id = trained_at.strftime(
        "%Y%m%dT%H%M%SZ"
    )

    training_end_date = pd.to_datetime(
        source["reference_date"]
    ).max()

    remote_base = (
        f"volume_forecast/"
        f"{MODEL_VERSION}/"
        f"{run_id}"
    )

    remote_model_path = (
        f"{remote_base}/model.npz"
    )

    remote_metadata_path = (
        f"{remote_base}/metadata.json"
    )

    metadata = {
        "model_version": MODEL_VERSION,
        "trained_at": trained_at.isoformat(),
        "training_end_date": str(
            training_end_date.date()
        ),
        "training_source": (
            f"{GOLD_FILE_SYSTEM}/"
            f"{GOLD_REMOTE_PATH}"
        ),
        "metrics": metrics,
    }

    save_model(
        LOCAL_MODEL_PATH,
        LOCAL_METADATA_PATH,
        coefficients,
        metadata,
    )

    print()
    print("Publicando modelo versionado no ADLS...")

    upload_file(
        local_path=LOCAL_MODEL_PATH,
        file_system=MODELS_FILE_SYSTEM,
        remote_path=remote_model_path,
    )

    upload_file(
        local_path=LOCAL_METADATA_PATH,
        file_system=MODELS_FILE_SYSTEM,
        remote_path=remote_metadata_path,
    )

    current = {
        "model_version": MODEL_VERSION,
        "trained_at": trained_at.isoformat(),
        "training_end_date": str(
            training_end_date.date()
        ),
        "model_path": remote_model_path,
        "metadata_path": remote_metadata_path,
    }

    LOCAL_CURRENT_PATH.write_text(
        json.dumps(
            current,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    # Atualizado por último de propósito:
    # só aponta para o novo modelo depois que os
    # artefatos já foram publicados com sucesso.
    upload_file(
        local_path=LOCAL_CURRENT_PATH,
        file_system=MODELS_FILE_SYSTEM,
        remote_path="volume_forecast/current.json",
    )

    # Cache local útil para testes e fallback de desenvolvimento.
    LOCAL_CACHE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    (LOCAL_CACHE_DIR / "current.npz").write_bytes(
        LOCAL_MODEL_PATH.read_bytes()
    )

    (LOCAL_CACHE_DIR / "metadata.json").write_bytes(
        LOCAL_METADATA_PATH.read_bytes()
    )

    print()
    print("TREINO_ADLS=SUCCESS")
    print(
        "Modelo:",
        f"{MODELS_FILE_SYSTEM}/{remote_model_path}",
    )
    print(
        "Current:",
        "models/volume_forecast/current.json",
    )


if __name__ == "__main__":
    main()