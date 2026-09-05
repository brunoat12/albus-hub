from __future__ import annotations

import numpy as np
import pandas as pd

from albus_hub.integration.risk_scores import calculate_risk_score, risk_level_from_score

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


def build_operational_scores(
    feature_frame: pd.DataFrame,
    breach_probability: np.ndarray,
    pressure_reference_p95: float,
) -> pd.DataFrame:
    """Combina probabilidade, prioridade e pressão na fórmula oficial 70/20/10."""
    priority_impact = (
        pd.to_numeric(feature_frame["priority_code"], errors="coerce")
        .map(PRIORITY_IMPACT)
        .fillna(0.0)
        .to_numpy(dtype=float)
    )
    denominator = max(float(pressure_reference_p95), 1.0)
    pressure = np.clip(
        feature_frame["assigned_group_incidents_previous_1d"].to_numpy(dtype=float) / denominator,
        0,
        1,
    )
    score = calculate_risk_score(breach_probability, priority_impact, pressure)
    level = risk_level_from_score(score)
    return pd.DataFrame(
        {
            "breach_probability": np.asarray(breach_probability, dtype=float),
            "priority_impact": priority_impact,
            "operational_pressure": pressure,
            "risk_score": score,
            "risk_level": level,
            "recommended_action": [RECOMMENDED_ACTIONS[value] for value in level],
        },
        index=feature_frame.index,
    )
