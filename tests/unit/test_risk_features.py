from __future__ import annotations

import pandas as pd
import pytest

from albus_hub.models.risk.contracts import RiskDataContractError, assert_no_leakage
from albus_hub.models.risk.features import build_risk_features


def build_silver_sample() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "incident_id": ["INC0000001", "INC0000002", "INC0000003"],
            "opened_at": pd.to_datetime(
                ["2025-01-01 00:00:00", "2025-01-02 00:00:00", "2025-01-02 00:00:00"]
            ),
            "closed_at": pd.to_datetime(
                ["2025-01-01 02:00:00", "2025-01-02 03:00:00", "2025-01-02 04:00:00"]
            ),
            "priority_code": pd.Series([2, 2, 2], dtype="Int64"),
            "product": ["p1", "p1", "p1"],
            "category": ["c1", "c1", "c1"],
            "subcategory": ["s1", "s1", "s1"],
            "assigned_group": ["team-a", "team-a", "team-a"],
            "configuration_item": ["ci-1", "ci-1", "ci-1"],
            "opened_by": ["Manual", "Manual", "Manual"],
            "entered_kpi_source": pd.Series([True, True, True], dtype="boolean"),
            "kpi_breached_source": pd.Series([False, True, False], dtype="boolean"),
        }
    )


def test_historical_features_are_strictly_previous() -> None:
    result = build_risk_features(build_silver_sample())
    simultaneous = result.loc[result["opened_at"].eq(pd.Timestamp("2025-01-02"))]

    assert simultaneous["assigned_group_incidents_previous_1d"].tolist() == [1, 1]
    assert simultaneous["assigned_group_known_outcomes_previous_30d"].tolist() == [1, 1]
    assert simultaneous["assigned_group_breaches_previous_30d"].tolist() == [0, 0]


def test_leakage_columns_are_rejected() -> None:
    with pytest.raises(RiskDataContractError, match="leakage"):
        assert_no_leakage(["priority_code", "resolved_at"])


def test_duplicate_incident_id_is_rejected() -> None:
    sample = build_silver_sample()
    sample.loc[1, "incident_id"] = sample.loc[0, "incident_id"]

    with pytest.raises(RiskDataContractError, match="único"):
        build_risk_features(sample)

