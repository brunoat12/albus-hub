from __future__ import annotations

import json
import os
import shutil
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from albus_hub.config import get_settings
from albus_hub.integration.risk_scores import validate_risk_scores
from albus_hub.models.risk.contracts import ELIGIBILITY_COLUMN
from albus_hub.models.risk.features import build_risk_features
from albus_hub.models.risk.inference import RiskPredictor
from albus_hub.storage.adls import download_file, upload_file
from albus_hub.storage.mysql import (
    MySQLRepository,
    create_mysql_engine,
)

STORAGE_ACCOUNT_ENV = "AZURE_STORAGE_ACCOUNT_NAME"

TRUSTED_FILE_SYSTEM = "trusted"
MODELS_FILE_SYSTEM = "models"
GOLD_FILE_SYSTEM = "gold"

TRUSTED_REMOTE_PATH = "ml/locaweb_incidents.parquet"
CURRENT_REMOTE_PATH = "risk/current.json"

RUNTIME_DIR = Path("artifacts/runtime/dl_risk_inference")
LOCAL_SOURCE_PATH = RUNTIME_DIR / "locaweb_incidents.parquet"
LOCAL_CURRENT_PATH = RUNTIME_DIR / "current.json"
LOCAL_MODEL_DIR = RUNTIME_DIR / "model"
LOCAL_OUTPUT_PATH = RUNTIME_DIR / "risk_scores.parquet"
LOCAL_STREAMLIT_OUTPUT = Path("data/gold/risk_scores.parquet")

REQUIRED_ARTIFACTS = (
    "ann.weights.h5",
    "preprocessor.joblib",
    "calibrator.joblib",
    "metadata.json",
)


def _load_current() -> dict:
    download_file(
        file_system=MODELS_FILE_SYSTEM,
        remote_path=CURRENT_REMOTE_PATH,
        local_path=LOCAL_CURRENT_PATH,
    )

    current = json.loads(LOCAL_CURRENT_PATH.read_text(encoding="utf-8"))

    model_version = current.get("model_version")
    artifacts = current.get("artifacts")

    if not model_version:
        raise RuntimeError("current.json sem model_version.")

    if not isinstance(artifacts, dict):
        raise RuntimeError("current.json sem mapa de artifacts.")

    missing = [name for name in REQUIRED_ARTIFACTS if name not in artifacts]

    if missing:
        raise RuntimeError(f"current.json incompleto. Artefatos ausentes: {missing}")

    return current


def _download_model(
    current: dict,
) -> None:
    artifacts = current["artifacts"]

    LOCAL_MODEL_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    for name in REQUIRED_ARTIFACTS:
        download_file(
            file_system=MODELS_FILE_SYSTEM,
            remote_path=artifacts[name],
            local_path=LOCAL_MODEL_DIR / name,
        )


def _to_mysql_rows(
    frame: pd.DataFrame,
) -> list[dict]:
    rows: list[dict] = []

    for row in frame.itertuples(index=False):
        scored_at = pd.Timestamp(row.scored_at)

        if scored_at.tzinfo is not None:
            scored_at = scored_at.tz_convert("UTC").tz_localize(None)

        rows.append(
            {
                "incident_id": str(row.incident_id),
                "scored_at": (scored_at.to_pydatetime()),
                "model_version": str(row.model_version),
                "breach_probability": float(row.breach_probability),
                "priority_impact": float(row.priority_impact),
                "operational_pressure": float(row.operational_pressure),
                "risk_score": int(row.risk_score),
                "risk_level": str(row.risk_level),
                "top_risk_factors": str(row.top_risk_factors),
                "recommended_action": str(row.recommended_action),
            }
        )

    return rows


def main() -> None:
    if not os.getenv(STORAGE_ACCOUNT_ENV):
        raise RuntimeError(f"{STORAGE_ACCOUNT_ENV} não está configurada.")

    print("=== INFERENCIA OPERACIONAL DL - RISK SCORE ===")

    if RUNTIME_DIR.exists():
        shutil.rmtree(RUNTIME_DIR)

    RUNTIME_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    print()
    print("Baixando Silver governada...")

    download_file(
        file_system=TRUSTED_FILE_SYSTEM,
        remote_path=TRUSTED_REMOTE_PATH,
        local_path=LOCAL_SOURCE_PATH,
    )

    print("Baixando ponteiro do modelo...")

    current = _load_current()

    print(
        "Modelo vigente:",
        current["model_version"],
    )

    _download_model(current)

    metadata = json.loads((LOCAL_MODEL_DIR / "metadata.json").read_text(encoding="utf-8"))

    if metadata["model_version"] != current["model_version"]:
        raise RuntimeError("model_version divergente entre current.json e metadata.json.")

    print()
    print("Construindo features...")

    silver = pd.read_parquet(LOCAL_SOURCE_PATH)

    features = build_risk_features(
        silver,
        require_targets=False,
    )

    features["opened_at"] = pd.to_datetime(
        features["opened_at"],
        errors="coerce",
    )

    eligible = features.loc[features[ELIGIBILITY_COLUMN].eq(True)].copy()

    if eligible.empty:
        raise RuntimeError("Nenhum incidente elegível para scoring.")

    reference_date = eligible["opened_at"].dt.date.max()

    cohort = eligible.loc[eligible["opened_at"].dt.date.eq(reference_date)].copy()

    if cohort.empty:
        raise RuntimeError("Coorte operacional vazia.")

    print(
        "Data de referência:",
        reference_date,
    )
    print(
        "Incidentes elegíveis:",
        len(cohort),
    )

    run_datetime = datetime.now(UTC)
    run_id = run_datetime.strftime("%Y%m%dT%H%M%SZ")

    predictor = RiskPredictor(LOCAL_MODEL_DIR)

    print()
    print("Executando scoring...")

    scores = predictor.predict_features(
        cohort.reset_index(drop=True),
        scored_at=pd.Timestamp(run_datetime),
    )

    scores = validate_risk_scores(scores)

    if len(scores) != len(cohort):
        raise RuntimeError("Quantidade de scores diverge da coorte operacional.")

    if scores["incident_id"].duplicated().any():
        raise RuntimeError("incident_id duplicado na saída operacional.")

    if set(scores["model_version"]) != {current["model_version"]}:
        raise RuntimeError("Versão inesperada nos scores.")

    LOCAL_OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    scores.to_parquet(
        LOCAL_OUTPUT_PATH,
        index=False,
    )

    remote_output = (
        f"ml/risk_scores/reference_date={reference_date}/run_id={run_id}/risk_scores.parquet"
    )

    print()
    print("Publicando Gold...")

    upload_file(
        local_path=LOCAL_OUTPUT_PATH,
        file_system=GOLD_FILE_SYSTEM,
        remote_path=remote_output,
    )

    print("Persistindo serving MySQL...")

    settings = get_settings()
    engine = create_mysql_engine(settings)

    try:
        repo = MySQLRepository(engine)

        repo.ensure_dl_risk_scores_table()

        mysql_rows = _to_mysql_rows(scores)

        repo.replace_dl_risk_scores(mysql_rows)

        stored = repo.fetch_dl_risk_scores()

        if len(stored) != len(mysql_rows):
            raise RuntimeError("Quantidade persistida no MySQL diverge da saída.")

        expected_ids = {str(value) for value in scores["incident_id"]}

        stored_ids = {str(row["incident_id"]) for row in stored}

        if stored_ids != expected_ids:
            raise RuntimeError("Conjunto de incident_id no MySQL diverge do scoring.")

    finally:
        engine.dispose()

    LOCAL_STREAMLIT_OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    shutil.copy2(
        LOCAL_OUTPUT_PATH,
        LOCAL_STREAMLIT_OUTPUT,
    )

    print()
    print("===== DISTRIBUICAO DE RISCO =====")

    distribution = scores["risk_level"].value_counts().sort_index()

    for level, count in distribution.items():
        print(
            level,
            "=",
            int(count),
        )

    print()
    print("===== MAIORES SCORES =====")

    top = scores.sort_values(
        [
            "risk_score",
            "breach_probability",
        ],
        ascending=False,
    ).head(10)[
        [
            "incident_id",
            "risk_score",
            "risk_level",
            "breach_probability",
        ]
    ]

    print(top.to_string(index=False))

    print()
    print("MYSQL_RISK_SCORES_REPLACE=SUCCESS")
    print("DL_RISK_INFERENCE_ADLS=SUCCESS")
    print(
        "Modelo:",
        current["model_version"],
    )
    print(
        "Reference date:",
        reference_date,
    )
    print(
        "Scores:",
        len(scores),
    )
    print(
        "Gold:",
        f"{GOLD_FILE_SYSTEM}/{remote_output}",
    )


if __name__ == "__main__":
    main()
