from __future__ import annotations

from pathlib import Path

import pandas as pd

REQUIRED_VOLUME_COLUMNS = {
    "reference_date",
    "generated_at",
    "horizon",
    "priority_scope",
    "predicted_incident_count",
    "model_version",
}

VALID_HORIZONS = {
    "D+1",
    "D+7",
}

VALID_PRIORITY_SCOPES = {
    "ALL",
    "P2",
    "P3",
}


class VolumePredictionContractError(ValueError):
    """Indica violação do contrato de previsões de volume."""


def validate_volume_predictions(
    frame: pd.DataFrame,
) -> pd.DataFrame:
    """Valida e normaliza o artefato de previsão D+1/D+7."""

    missing = REQUIRED_VOLUME_COLUMNS - set(frame.columns)

    if missing:
        raise VolumePredictionContractError(
            f"Colunas obrigatórias ausentes nas previsões de volume: {sorted(missing)}"
        )

    result = frame.copy()

    result["reference_date"] = pd.to_datetime(
        result["reference_date"],
        errors="coerce",
    ).dt.normalize()

    result["generated_at"] = pd.to_datetime(
        result["generated_at"],
        errors="coerce",
    )

    if result["reference_date"].isna().any():
        raise VolumePredictionContractError("reference_date possui valores inválidos.")

    if result["generated_at"].isna().any():
        raise VolumePredictionContractError("generated_at possui valores inválidos.")

    result["horizon"] = result["horizon"].astype("string").str.strip().str.upper()

    invalid_horizons = set(result["horizon"].dropna()) - VALID_HORIZONS

    if invalid_horizons:
        raise VolumePredictionContractError(
            f"horizon contém valores inválidos: {sorted(invalid_horizons)}"
        )

    result["priority_scope"] = result["priority_scope"].astype("string").str.strip().str.upper()

    invalid_scopes = set(result["priority_scope"].dropna()) - VALID_PRIORITY_SCOPES

    if invalid_scopes:
        raise VolumePredictionContractError(
            f"priority_scope contém valores inválidos: {sorted(invalid_scopes)}"
        )

    result["predicted_incident_count"] = pd.to_numeric(
        result["predicted_incident_count"],
        errors="coerce",
    )

    invalid_prediction = result["predicted_incident_count"].isna() | (
        result["predicted_incident_count"] < 0
    )

    if invalid_prediction.any():
        raise VolumePredictionContractError(
            "predicted_incident_count deve ser numérico e não negativo."
        )

    result["model_version"] = result["model_version"].astype("string").str.strip()

    if result["model_version"].isna().any() or result["model_version"].eq("").any():
        raise VolumePredictionContractError("model_version possui valores ausentes.")

    duplicated_key = result.duplicated(
        subset=[
            "reference_date",
            "horizon",
            "priority_scope",
            "model_version",
        ],
        keep=False,
    )

    if duplicated_key.any():
        raise VolumePredictionContractError(
            "A chave lógica reference_date + horizon + "
            "priority_scope + model_version possui duplicidades."
        )

    return result


def load_volume_predictions(
    path: Path,
) -> pd.DataFrame | None:
    """
    Carrega previsões D+1/D+7.

    Retorna None enquanto o artefato ainda não tiver sido
    entregue pelo modelo.
    """

    if not path.exists():
        return None

    frame = pd.read_parquet(path)

    return validate_volume_predictions(frame)
