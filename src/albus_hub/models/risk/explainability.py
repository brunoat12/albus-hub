from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pandas as pd

EXPLANATION_FEATURES = [
    "priority_code",
    "product",
    "category",
    "assigned_group",
    "configuration_item",
    "opened_by",
    "opened_hour",
    "opened_day_of_week",
    "assigned_group_incidents_previous_1d",
    "assigned_group_incidents_previous_7d",
    "assigned_group_breach_rate_previous_30d",
    "product_incidents_previous_7d",
    "category_incidents_previous_7d",
]

FEATURE_LABELS = {
    "priority_code": "prioridade",
    "product": "produto",
    "category": "categoria",
    "assigned_group": "equipe",
    "configuration_item": "item de configuração",
    "opened_by": "origem da abertura",
    "opened_hour": "hora de abertura",
    "opened_day_of_week": "dia da semana",
    "assigned_group_incidents_previous_1d": "carga da equipe nas 24h anteriores",
    "assigned_group_incidents_previous_7d": "carga da equipe nos 7 dias anteriores",
    "assigned_group_breach_rate_previous_30d": "taxa histórica da equipe em 30 dias",
    "product_incidents_previous_7d": "volume do produto nos 7 dias anteriores",
    "category_incidents_previous_7d": "volume da categoria nos 7 dias anteriores",
}


def build_reference_values(training_features: pd.DataFrame) -> dict[str, object]:
    """Cria valores típicos do treino usados na explicação por perturbação."""
    references: dict[str, object] = {}
    for column in EXPLANATION_FEATURES:
        series = training_features[column]
        if pd.api.types.is_numeric_dtype(series):
            references[column] = float(series.median())
        else:
            mode = series.dropna().mode()
            references[column] = mode.iloc[0] if not mode.empty else "__MISSING__"
    return references


def _format_factor(column: str, value: object) -> str:
    label = FEATURE_LABELS[column]
    if pd.isna(value):
        rendered = "sem informação"
    elif column == "priority_code":
        rendered = f"P{int(value)}"
    elif column == "assigned_group_breach_rate_previous_30d":
        rendered = f"{100 * float(value):.2f}%"
    elif isinstance(value, (float, np.floating)):
        rendered = f"{float(value):.1f}"
    else:
        rendered = str(value)
    return f"{label}: {rendered}"


def explain_by_perturbation(
    feature_frame: pd.DataFrame,
    base_probabilities: np.ndarray,
    reference_values: dict[str, object],
    predict_probability: Callable[[pd.DataFrame], np.ndarray],
    top_n: int = 3,
) -> list[str]:
    """Explica localmente pela queda de probabilidade ao neutralizar cada feature."""
    perturbed_frames = []
    for column in EXPLANATION_FEATURES:
        perturbed = feature_frame.copy()
        perturbed[column] = reference_values[column]
        perturbed_frames.append(perturbed)
    perturbed_probabilities = predict_probability(
        pd.concat(perturbed_frames, ignore_index=True)
    ).reshape(len(EXPLANATION_FEATURES), len(feature_frame))
    contributions = np.asarray(base_probabilities)[:, None] - perturbed_probabilities.T

    explanations = []
    for row_index in range(len(feature_frame)):
        order = np.argsort(contributions[row_index])[::-1]
        positive = [index for index in order if contributions[row_index, index] > 1e-6]
        selected = positive[:top_n]
        if not selected:
            explanations.append("sem fator positivo dominante")
            continue
        factors = [
            _format_factor(
                EXPLANATION_FEATURES[index],
                feature_frame.iloc[row_index][EXPLANATION_FEATURES[index]],
            )
            for index in selected
        ]
        explanations.append("; ".join(factors))
    return explanations
