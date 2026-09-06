from __future__ import annotations

import numpy as np
from sklearn.linear_model import LogisticRegression


def probability_logit(probabilities: np.ndarray) -> np.ndarray:
    """Transforma probabilidades em logits com proteção numérica."""
    clipped = np.clip(np.asarray(probabilities, dtype=float), 1e-6, 1 - 1e-6)
    return np.log(clipped / (1 - clipped)).reshape(-1, 1)


def fit_probability_calibrator(
    probabilities: np.ndarray,
    target: np.ndarray,
) -> LogisticRegression:
    """Ajusta calibração de Platt exclusivamente na janela de validação."""
    calibrator = LogisticRegression(random_state=42)
    calibrator.fit(probability_logit(probabilities), np.asarray(target, dtype=int))
    return calibrator


def apply_probability_calibrator(calibrator, probabilities: np.ndarray) -> np.ndarray:
    """Aplica a calibração salva sem reestimar parâmetros."""
    return calibrator.predict_proba(probability_logit(probabilities))[:, 1]

