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
            "reference_date": ["2026-01-01"],
            "generated_at": ["2026-08-30T12:00:00"],
            "horizon": ["D+1"],
            "priority_scope": ["P4"],
            "predicted_incident_count": [367.0],
            "lower_bound": [300.25],
            "upper_bound": [433.75],
            "model_name": ["ultimo"],
            "model_version": ["volume_v3.2_2026-08-21"],
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
        == "P4"
    )


def test_invalid_horizon_fails() -> None:
    frame = build_valid_prediction_frame()

    frame.loc[
        0,
        "horizon",
    ] = "D+30"

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
    ] = "P6"

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


def test_invalid_interval_fails() -> None:
    frame = build_valid_prediction_frame()

    frame.loc[
        0,
        "lower_bound",
    ] = 400

    with pytest.raises(
        VolumePredictionContractError,
        match="Intervalo inválido",
    ):
        validate_volume_predictions(frame)


def test_missing_model_name_fails() -> None:
    frame = build_valid_prediction_frame()

    frame.loc[
        0,
        "model_name",
    ] = ""

    with pytest.raises(
        VolumePredictionContractError,
        match="model_name",
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
