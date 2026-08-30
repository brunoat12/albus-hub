from __future__ import annotations

import pandas as pd
import pytest

from albus_hub.integration.risk_scores import (
    RiskScoreContractError,
    load_risk_scores,
    validate_risk_scores,
)


def build_valid_risk_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "incident_id": ["INC1234567"],
            "scored_at": ["2026-08-09T12:00:00"],
            "model_version": ["risk-model-v1"],
            "breach_probability": [0.74],
            "priority_impact": [0.80],
            "operational_pressure": [0.60],
            "risk_score": [74],
            "risk_level": ["alto"],
            "top_risk_factors": ["prioridade; pressão operacional"],
            "recommended_action": ["Priorizar atendimento."],
        }
    )


def test_valid_risk_score_contract() -> None:
    frame = build_valid_risk_frame()

    result = validate_risk_scores(frame)

    assert len(result) == 1
    assert result.loc[0, "risk_score"] == 74
    assert result.loc[0, "risk_level"] == "alto"


def test_risk_score_outside_range_fails() -> None:
    frame = build_valid_risk_frame()
    frame.loc[0, "risk_score"] = 120

    with pytest.raises(
        RiskScoreContractError,
        match="0 e 100",
    ):
        validate_risk_scores(frame)


def test_probability_outside_range_fails() -> None:
    frame = build_valid_risk_frame()
    frame.loc[
        0,
        "breach_probability",
    ] = 1.5

    with pytest.raises(
        RiskScoreContractError,
        match="0 e 1",
    ):
        validate_risk_scores(frame)


def test_score_formula_mismatch_fails() -> None:
    frame = build_valid_risk_frame()
    frame.loc[0, "risk_score"] = 73

    with pytest.raises(RiskScoreContractError, match="fórmula oficial"):
        validate_risk_scores(frame)


def test_risk_level_mismatch_fails() -> None:
    frame = build_valid_risk_frame()
    frame.loc[0, "risk_level"] = "crítico"

    with pytest.raises(RiskScoreContractError, match="não corresponde"):
        validate_risk_scores(frame)


def test_explanation_must_be_filled() -> None:
    frame = build_valid_risk_frame()
    frame.loc[0, "top_risk_factors"] = ""

    with pytest.raises(RiskScoreContractError, match="top_risk_factors"):
        validate_risk_scores(frame)


def test_duplicate_logical_key_fails() -> None:
    frame = pd.concat(
        [
            build_valid_risk_frame(),
            build_valid_risk_frame(),
        ],
        ignore_index=True,
    )

    with pytest.raises(
        RiskScoreContractError,
        match="duplicidades",
    ):
        validate_risk_scores(frame)


def test_missing_risk_artifact_returns_none(
    tmp_path,
) -> None:
    result = load_risk_scores(tmp_path / "risk_scores.parquet")

    assert result is None
