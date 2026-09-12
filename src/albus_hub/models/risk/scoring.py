from __future__ import annotations

import numpy as np
import pandas as pd

from albus_hub.integration.risk_scores import (
    calculate_risk_score,
    risk_level_from_score,
)

PRIORITY_IMPACT = {
    1: 1.00,
    2: 0.80,
    3: 0.60,
    4: 0.30,
    5: 0.10,
}

RECOMMENDED_ACTIONS = {
    "baixo": "Acompanhamento normal do incidente.",
    "moderado": "Acompanhar evolução e capacidade da equipe responsável.",
    "alto": "Priorizar investigação preventiva e revisar a fila da equipe.",
    "crítico": "Priorizar atendimento e avaliar escalonamento imediato.",
}


def predictive_risk_percentile(
    breach_probability: np.ndarray,
    reference_distribution: np.ndarray,
) -> np.ndarray:
    """
    Converte probabilidades calibradas em posição relativa histórica.

    O valor retornado está entre 0 e 1 e representa o percentil
    da probabilidade em relação a uma distribuição de referência
    construída sem utilizar o conjunto de teste.
    """

    probabilities = np.asarray(
        breach_probability,
        dtype=float,
    )

    reference = np.asarray(
        reference_distribution,
        dtype=float,
    )

    reference = reference[np.isfinite(reference)]

    if reference.size == 0:
        raise ValueError("A distribuição histórica de referência do Risk Score está vazia.")

    reference = np.sort(reference)

    percentile = (
        np.searchsorted(
            reference,
            probabilities,
            side="right",
        )
        / reference.size
    )

    return np.clip(
        percentile,
        0.0,
        1.0,
    )


def build_operational_scores(
    feature_frame: pd.DataFrame,
    breach_probability: np.ndarray,
    pressure_reference_p95: float,
    predictive_reference: np.ndarray,
) -> pd.DataFrame:
    """
    Combina risco preditivo, prioridade e pressão no Risk Score v2.

    Fórmula:
        80% predictive_risk_index
        15% priority_impact
         5% operational_pressure

    breach_probability continua sendo armazenada separadamente e
    representa a probabilidade calibrada real do modelo champion.
    """

    probability = np.asarray(
        breach_probability,
        dtype=float,
    )

    predictive_risk_index = predictive_risk_percentile(
        probability,
        predictive_reference,
    )

    priority_impact = (
        pd.to_numeric(
            feature_frame["priority_code"],
            errors="coerce",
        )
        .map(PRIORITY_IMPACT)
        .fillna(0.0)
        .to_numpy(dtype=float)
    )

    denominator = max(
        float(pressure_reference_p95),
        1.0,
    )

    pressure = np.clip(
        pd.to_numeric(
            feature_frame["assigned_group_incidents_previous_1d"],
            errors="coerce",
        )
        .fillna(0.0)
        .to_numpy(dtype=float)
        / denominator,
        0,
        1,
    )

    score = calculate_risk_score(
        predictive_risk_index,
        priority_impact,
        pressure,
    )

    level = risk_level_from_score(score)

    return pd.DataFrame(
        {
            "breach_probability": probability,
            "predictive_risk_index": predictive_risk_index,
            "priority_impact": priority_impact,
            "operational_pressure": pressure,
            "risk_score": score,
            "risk_level": level,
            "recommended_action": [RECOMMENDED_ACTIONS[value] for value in level],
        },
        index=feature_frame.index,
    )
