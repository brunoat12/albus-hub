from __future__ import annotations

from pathlib import Path

import pandas as pd

REQUIRED_VOLUME_COLUMNS = {
    "reference_date",
    "generated_at",
    "horizon",
    "priority_scope",
    "predicted_incident_count",
    "lower_bound",
    "upper_bound",
    "model_name",
    "model_version",
}

VALID_HORIZONS = {
    "D+1",
    "D+7",
}

VALID_PRIORITY_SCOPES = {
    "ALL",
    "P1",
    "P2",
    "P3",
    "P4",
    "P5",
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

    numeric_columns = [
        "predicted_incident_count",
        "lower_bound",
        "upper_bound",
    ]

    for column in numeric_columns:
        result[column] = pd.to_numeric(
            result[column],
            errors="coerce",
        )

        invalid = result[column].isna() | (result[column] < 0)

        if invalid.any():
            raise VolumePredictionContractError(f"{column} deve ser numérico e não negativo.")

    invalid_interval = (
        (result["lower_bound"] > result["predicted_incident_count"])
        | (result["upper_bound"] < result["predicted_incident_count"])
        | (result["lower_bound"] > result["upper_bound"])
    )

    if invalid_interval.any():
        raise VolumePredictionContractError(
            "Intervalo inválido: deve respeitar "
            "lower_bound <= predicted_incident_count "
            "<= upper_bound."
        )

    result["model_name"] = result["model_name"].astype("string").str.strip()

    if result["model_name"].isna().any() or result["model_name"].eq("").any():
        raise VolumePredictionContractError("model_name possui valores ausentes.")

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
    """Carrega previsões D+1/D+7."""

    if not path.exists():
        return None

    frame = pd.read_parquet(path)

    return validate_volume_predictions(frame)
