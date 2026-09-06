from __future__ import annotations

import pandas as pd
import pytest

from albus_hub.integration.volume_predictions import (
    VolumePredictionContractError,
    load_volume_predictions,
    validate_volume_predictions,
)


def build_valid_prediction_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "reference_date": ["2026-08-09"],
            "generated_at": ["2026-08-09T12:00:00"],
            "horizon": ["D+1"],
            "priority_scope": ["P2"],
            "predicted_incident_count": [145.3],
            "model_version": ["volume-model-v1"],
        }
    )


def test_valid_volume_prediction_contract() -> None:
    frame = build_valid_prediction_frame()

    result = validate_volume_predictions(frame)

    assert len(result) == 1
    assert result.loc[0, "horizon"] == "D+1"
    assert (
        result.loc[
            0,
            "priority_scope",
        ]
        == "P2"
    )


def test_invalid_horizon_fails() -> None:
    frame = build_valid_prediction_frame()
    frame.loc[0, "horizon"] = "D+30"

    with pytest.raises(
        VolumePredictionContractError,
        match="horizon",
    ):
        validate_volume_predictions(frame)


def test_invalid_priority_scope_fails() -> None:
    frame = build_valid_prediction_frame()
    frame.loc[
        0,
        "priority_scope",
    ] = "P4"

    with pytest.raises(
        VolumePredictionContractError,
        match="priority_scope",
    ):
        validate_volume_predictions(frame)


def test_negative_prediction_fails() -> None:
    frame = build_valid_prediction_frame()
    frame.loc[
        0,
        "predicted_incident_count",
    ] = -10

    with pytest.raises(
        VolumePredictionContractError,
        match="não negativo",
    ):
        validate_volume_predictions(frame)


def test_duplicate_prediction_key_fails() -> None:
    frame = pd.concat(
        [
            build_valid_prediction_frame(),
            build_valid_prediction_frame(),
        ],
        ignore_index=True,
    )

    with pytest.raises(
        VolumePredictionContractError,
        match="duplicidades",
    ):
        validate_volume_predictions(frame)


def test_missing_prediction_artifact_returns_none(
    tmp_path,
) -> None:
    result = load_volume_predictions(tmp_path / "volume_predictions.parquet")

    assert result is None
