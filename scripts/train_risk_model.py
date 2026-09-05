from __future__ import annotations

import json
import os
import shutil
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from albus_hub.models.risk.train import RiskTrainingConfig, train_risk_model
from albus_hub.storage.adls import download_file, upload_file

STORAGE_ACCOUNT_ENV = "AZURE_STORAGE_ACCOUNT_NAME"

TRUSTED_FILE_SYSTEM = "trusted"
MODELS_FILE_SYSTEM = "models"

TRUSTED_REMOTE_PATH = "ml/locaweb_incidents.parquet"
CURRENT_REMOTE_PATH = "risk/current.json"

MODEL_VERSION = "risk-ann-v1-20260820"

RUNTIME_DIR = Path("artifacts/runtime/dl_risk_training")
LOCAL_SOURCE_PATH = RUNTIME_DIR / "locaweb_incidents.parquet"
LOCAL_MODEL_DIR = RUNTIME_DIR / "model"
LOCAL_FEATURES_PATH = RUNTIME_DIR / "risk_features.parquet"
LOCAL_SCORES_PATH = RUNTIME_DIR / "risk_scores.parquet"
LOCAL_METRICS_PATH = RUNTIME_DIR / "metrics.json"
LOCAL_FIGURES_DIR = RUNTIME_DIR / "figures"
LOCAL_CURRENT_PATH = RUNTIME_DIR / "current.json"

MODEL_ARTIFACTS = (
    "ann.weights.h5",
    "preprocessor.joblib",
    "calibrator.joblib",
    "metadata.json",
    "baseline_logistic.joblib",
)


def main() -> None:
    if not os.getenv(STORAGE_ACCOUNT_ENV):
        raise RuntimeError(f"{STORAGE_ACCOUNT_ENV} não está configurada.")

    print("=== TREINO OPERACIONAL DL - RISK SCORE ===")
    print(
        "Fonte oficial:",
        f"{TRUSTED_FILE_SYSTEM}/{TRUSTED_REMOTE_PATH}",
    )

    if RUNTIME_DIR.exists():
        shutil.rmtree(RUNTIME_DIR)

    LOCAL_MODEL_DIR.mkdir(parents=True, exist_ok=True)
    LOCAL_FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    print()
    print("Baixando Silver governada do ADLS...")

    download_file(
        file_system=TRUSTED_FILE_SYSTEM,
        remote_path=TRUSTED_REMOTE_PATH,
        local_path=LOCAL_SOURCE_PATH,
    )

    silver = pd.read_parquet(LOCAL_SOURCE_PATH)

    opened_at = pd.to_datetime(
        silver["opened_at"],
        errors="coerce",
    )

    if opened_at.isna().all():
        raise RuntimeError("Não foi possível determinar o período da Silver.")

    training_end_date = opened_at.max().date().isoformat()

    print(
        "Linhas:",
        len(silver),
    )
    print(
        "Training end:",
        training_end_date,
    )

    config = RiskTrainingConfig(
        silver_path=LOCAL_SOURCE_PATH,
        risk_features_path=LOCAL_FEATURES_PATH,
        risk_scores_path=LOCAL_SCORES_PATH,
        model_dir=LOCAL_MODEL_DIR,
        metrics_path=LOCAL_METRICS_PATH,
        figures_dir=LOCAL_FIGURES_DIR,
        model_version=MODEL_VERSION,
    )

    print()
    print("Executando treino canônico...")

    metrics = train_risk_model(config)

    missing = [name for name in MODEL_ARTIFACTS if not (LOCAL_MODEL_DIR / name).exists()]

    if missing:
        raise RuntimeError(f"Artefatos de modelo ausentes: {missing}")

    if not LOCAL_METRICS_PATH.exists():
        raise RuntimeError("metrics.json não foi gerado.")

    metadata_path = LOCAL_MODEL_DIR / "metadata.json"

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

    if metadata["model_version"] != MODEL_VERSION:
        raise RuntimeError("Versão divergente nos metadados.")

    training_source = f"{TRUSTED_FILE_SYSTEM}/{TRUSTED_REMOTE_PATH}"

    metadata["training_source"] = training_source
    metadata["training_end_date"] = training_end_date

    metadata_path.write_text(
        json.dumps(
            metadata,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")

    remote_base = f"risk/{MODEL_VERSION}/{run_id}"

    print()
    print("Publicando artefatos versionados...")

    artifact_paths: dict[str, str] = {}

    for name in MODEL_ARTIFACTS:
        remote_path = f"{remote_base}/{name}"

        upload_file(
            local_path=LOCAL_MODEL_DIR / name,
            file_system=MODELS_FILE_SYSTEM,
            remote_path=remote_path,
        )

        artifact_paths[name] = remote_path

    metrics_remote_path = f"{remote_base}/metrics.json"

    upload_file(
        local_path=LOCAL_METRICS_PATH,
        file_system=MODELS_FILE_SYSTEM,
        remote_path=metrics_remote_path,
    )

    current = {
        "model_version": MODEL_VERSION,
        "artifact_format": "keras-weights+joblib",
        "trained_at": metadata["created_at_utc"],
        "training_end_date": training_end_date,
        "training_source": training_source,
        "selected_ann": metrics["selected_ann"],
        "selected_threshold": metrics["selected_threshold"],
        "artifacts": {
            **artifact_paths,
            "metrics.json": metrics_remote_path,
        },
    }

    LOCAL_CURRENT_PATH.write_text(
        json.dumps(
            current,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    # O ponteiro é sempre publicado por último.
    upload_file(
        local_path=LOCAL_CURRENT_PATH,
        file_system=MODELS_FILE_SYSTEM,
        remote_path=CURRENT_REMOTE_PATH,
    )

    print()
    print("DL_TREINO_ADLS=SUCCESS")
    print("Modelo:", MODEL_VERSION)
    print("ANN:", metrics["selected_ann"])
    print(
        "Threshold:",
        metrics["selected_threshold"],
    )
    print(
        "Artefatos:",
        len(artifact_paths),
    )
    print(
        "Current:",
        f"{MODELS_FILE_SYSTEM}/{CURRENT_REMOTE_PATH}",
    )


if __name__ == "__main__":
    main()
