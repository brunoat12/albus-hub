from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd

from albus_hub.storage.mysql import dl_risk_scores_current_table


def _load_risk_inference_module():
    path = Path(__file__).resolve().parents[2] / "scripts" / "run_risk_inference.py"

    spec = importlib.util.spec_from_file_location(
        "run_risk_inference_test_module",
        path,
    )

    if spec is None or spec.loader is None:
        raise RuntimeError("Não foi possível carregar scripts/run_risk_inference.py")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    return module


risk_inference = _load_risk_inference_module()


def test_operational_inference_requires_champion_artifacts() -> None:
    assert risk_inference.REQUIRED_ARTIFACTS == (
        "preprocessor.joblib",
        "baseline_logistic.joblib",
        "baseline_calibrator.joblib",
        "predictive_reference.npy",
        "metadata.json",
    )

    assert "ann.weights.h5" not in risk_inference.REQUIRED_ARTIFACTS

    assert "calibrator.joblib" not in risk_inference.REQUIRED_ARTIFACTS


def test_mysql_schema_contains_predictive_risk_index() -> None:
    columns = set(dl_risk_scores_current_table.columns.keys())

    expected = {
        "incident_id",
        "scored_at",
        "model_version",
        "breach_probability",
        "predictive_risk_index",
        "priority_impact",
        "operational_pressure",
        "risk_score",
        "risk_level",
        "top_risk_factors",
        "recommended_action",
        "updated_at",
    }

    assert expected.issubset(columns)


def test_mysql_row_conversion_preserves_risk_v2_contract() -> None:
    frame = pd.DataFrame(
        {
            "incident_id": ["INC0000001"],
            "scored_at": [pd.Timestamp("2026-09-10T12:00:00Z")],
            "model_version": ["risk-logistic-v2-20260910"],
            "breach_probability": [0.025],
            "predictive_risk_index": [0.74],
            "priority_impact": [0.80],
            "operational_pressure": [0.60],
            "risk_score": [74],
            "risk_level": ["alto"],
            "top_risk_factors": ["risco preditivo; prioridade"],
            "recommended_action": ["Priorizar atendimento."],
        }
    )

    rows = risk_inference._to_mysql_rows(frame)

    assert len(rows) == 1

    row = rows[0]

    assert row["incident_id"] == "INC0000001"
    assert row["model_version"] == ("risk-logistic-v2-20260910")
    assert row["breach_probability"] == 0.025
    assert row["predictive_risk_index"] == 0.74
    assert row["priority_impact"] == 0.80
    assert row["operational_pressure"] == 0.60
    assert row["risk_score"] == 74
    assert row["risk_level"] == "alto"

    assert row["scored_at"].tzinfo is None
