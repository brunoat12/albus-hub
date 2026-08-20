from __future__ import annotations

import numpy as np
import pandas as pd

from albus_hub.integration.risk_scores import calculate_risk_score, risk_level_from_score
from albus_hub.models.risk.contracts import MODEL_FEATURES
from albus_hub.models.risk.model import ANNConfig, build_ann
from albus_hub.models.risk.preprocessing import build_preprocessor


def test_score_formula_and_levels() -> None:
    scores = calculate_risk_score(
        np.array([0.0, 0.74, 1.0]),
        np.array([0.0, 0.8, 1.0]),
        np.array([0.0, 0.6, 1.0]),
    )

    assert scores.tolist() == [0, 74, 100]
    assert risk_level_from_score(scores).tolist() == ["baixo", "alto", "crítico"]


def test_preprocessor_accepts_unknown_categories() -> None:
    base = {column: [0, 1] for column in MODEL_FEATURES}
    for column in [
        "priority_code",
        "product",
        "category",
        "subcategory",
        "assigned_group",
        "configuration_item",
        "opened_by",
    ]:
        base[column] = ["known-a", "known-b"]
    training = pd.DataFrame(base)
    unknown = training.iloc[[0]].copy()
    unknown["product"] = "never-seen"
    preprocessor = build_preprocessor()

    preprocessor.fit(training)
    transformed = preprocessor.transform(unknown)

    assert transformed.shape[0] == 1
    assert np.isfinite(transformed).all()


def test_ann_has_sigmoid_binary_output() -> None:
    config = ANNConfig(
        name="test",
        hidden_units=(8, 4),
        dropout=0.2,
        learning_rate=0.001,
        epochs=1,
    )
    model = build_ann(10, config)

    assert model.output_shape == (None, 1)
    assert model.layers[-1].activation.__name__ == "sigmoid"
