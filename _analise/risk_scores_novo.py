from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

REQUIRED_RISK_COLUMNS = {
    "incident_id",
    "scored_at",
    "model_version",
    "breach_probability",
    "priority_impact",
    "operational_pressure",
    "risk_score",
    "risk_level",
    "top_risk_factors",
    "recommended_action",
}

RISK_LEVELS = {
    "baixo",
    "moderado",
    "alto",
    "crítico",
}

RISK_SCORE_WEIGHTS = {
    "breach_probability": 0.70,
    "priority_impact": 0.20,
    "operational_pressure": 0.10,
}


def calculate_risk_score(
    breach_probability,
    priority_impact,
    operational_pressure,
) -> np.ndarray:
    """Calcula o score operacional oficial e aplica arredondamento para 0–100."""
    weighted = 100 * (
        RISK_SCORE_WEIGHTS["breach_probability"] * np.asarray(breach_probability)
        + RISK_SCORE_WEIGHTS["priority_impact"] * np.asarray(priority_impact)
        + RISK_SCORE_WEIGHTS["operational_pressure"] * np.asarray(operational_pressure)
    )
    return np.floor(weighted + 0.5).clip(0, 100).astype("int64")


def risk_level_from_score(score) -> np.ndarray:
    """Converte scores nos níveis em português aceitos pelo dashboard."""
    values = np.asarray(score, dtype=float)
    return np.select(
        [values <= 24, values <= 49, values <= 74],
        ["baixo", "moderado", "alto"],
        default="crítico",
    )


class RiskScoreContractError(ValueError):
    """Indica que o artefato de score não respeita o contrato."""


def validate_risk_scores(
    frame: pd.DataFrame,
) -> pd.DataFrame:
    """Valida e normaliza o contrato de score de risco."""

    missing = REQUIRED_RISK_COLUMNS - set(frame.columns)

    if missing:
        raise RiskScoreContractError(
            f"Colunas obrigatórias ausentes no score de risco: {sorted(missing)}"
        )

    result = frame.copy()

    result["incident_id"] = result["incident_id"].astype("string").str.strip()

    result["model_version"] = result["model_version"].astype("string").str.strip()

    result["scored_at"] = pd.to_datetime(
        result["scored_at"],
        errors="coerce",
    )

    numeric_columns = [
        "breach_probability",
        "priority_impact",
        "operational_pressure",
        "risk_score",
    ]

    for column in numeric_columns:
        result[column] = pd.to_numeric(
            result[column],
            errors="coerce",
        )

    if result["incident_id"].isna().any():
        raise RiskScoreContractError("incident_id possui valores nulos.")

    if result["scored_at"].isna().any():
        raise RiskScoreContractError("scored_at possui valores inválidos.")

    if result["model_version"].isna().any():
        raise RiskScoreContractError("model_version possui valores nulos.")

    probability_columns = [
        "breach_probability",
        "priority_impact",
        "operational_pressure",
    ]

    for column in probability_columns:
        invalid = result[column].isna() | ~result[column].between(
            0,
            1,
            inclusive="both",
        )

        if invalid.any():
            raise RiskScoreContractError(f"{column} deve possuir valores entre 0 e 1.")

    invalid_score = result["risk_score"].isna() | ~result["risk_score"].between(
        0,
        100,
        inclusive="both",
    )

    if invalid_score.any():
        raise RiskScoreContractError("risk_score deve possuir valores entre 0 e 100.")

    result["risk_score"] = result["risk_score"].round().astype("int64")

    result["risk_level"] = result["risk_level"].astype("string").str.strip().str.lower()

    invalid_levels = set(result["risk_level"].dropna()) - RISK_LEVELS

    if result["risk_level"].isna().any() or invalid_levels:
        raise RiskScoreContractError(
            f"risk_level contém valores inválidos: {sorted(invalid_levels)}"
        )

    expected_scores = calculate_risk_score(
        result["breach_probability"],
        result["priority_impact"],
        result["operational_pressure"],
    )
    if not np.array_equal(result["risk_score"].to_numpy(), expected_scores):
        raise RiskScoreContractError("risk_score não respeita a fórmula oficial 70/20/10.")

    expected_levels = risk_level_from_score(result["risk_score"])
    if not np.array_equal(result["risk_level"].to_numpy(dtype=str), expected_levels):
        raise RiskScoreContractError("risk_level não corresponde à faixa do risk_score.")

    for column in ["top_risk_factors", "recommended_action"]:
        result[column] = result[column].astype("string").str.strip()
        if result[column].isna().any() or result[column].eq("").any():
            raise RiskScoreContractError(f"{column} deve ser preenchido.")

    duplicated_key = result.duplicated(
        subset=[
            "incident_id",
            "scored_at",
            "model_version",
        ],
        keep=False,
    )

    if duplicated_key.any():
        raise RiskScoreContractError(
            "A chave lógica incident_id + scored_at + model_version possui duplicidades."
        )

    return result


def load_risk_scores(
    path: Path,
) -> pd.DataFrame | None:
    """
    Carrega o artefato de score.

    Retorna None quando o modelo ainda não entregou
    o artefato, permitindo que consumidores como
    Streamlit funcionem sem depender do modelo.
    """

    if not path.exists():
        return None

    frame = pd.read_parquet(path)

    return validate_risk_scores(frame)
