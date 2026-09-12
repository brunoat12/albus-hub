from __future__ import annotations

import inspect

from albus_hub.models.risk.train import (
    CHAMPION_C,
    FINAL_TEST_START,
    FINAL_TRAIN_END,
    FINAL_VALIDATION_MONTHS,
    RiskTrainingConfig,
    _build_logistic_oof,
    _fit_logistic_model,
    train_risk_model,
)


def test_risk_training_module_exposes_final_protocol() -> None:
    assert CHAMPION_C == 0.01

    assert FINAL_VALIDATION_MONTHS == (
        "2025-04",
        "2025-05",
        "2025-06",
        "2025-07",
        "2025-08",
        "2025-09",
    )

    assert str(FINAL_TRAIN_END) == "2025-09"
    assert str(FINAL_TEST_START) == "2025-10"


def test_risk_training_functions_are_importable() -> None:
    assert callable(train_risk_model)
    assert callable(_build_logistic_oof)
    assert callable(_fit_logistic_model)

    assert inspect.isfunction(train_risk_model)

    assert inspect.isfunction(_build_logistic_oof)

    assert inspect.isfunction(_fit_logistic_model)


def test_default_model_version_points_to_champion() -> None:
    fields = RiskTrainingConfig.__dataclass_fields__

    assert fields["model_version"].default == "risk-logistic-v2-20260910"
