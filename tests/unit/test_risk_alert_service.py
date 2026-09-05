from datetime import UTC, datetime
from unittest.mock import MagicMock

import pandas as pd

from albus_hub.alerts.service import (
    publish_risk_alerts,
)


def _scores() -> pd.DataFrame:
    scored_at = datetime(
        2026,
        9,
        4,
        20,
        45,
        tzinfo=UTC,
    )

    return pd.DataFrame(
        [
            {
                "incident_id": "INC-LOW",
                "scored_at": scored_at,
                "model_version": "risk-ann-v1-20260820",
                "breach_probability": 0.10,
                "risk_score": 18,
                "risk_level": "baixo",
                "top_risk_factors": "",
                "recommended_action": "Acompanhamento normal.",
            },
            {
                "incident_id": "INC-MOD",
                "scored_at": scored_at,
                "model_version": "risk-ann-v1-20260820",
                "breach_probability": 0.35,
                "risk_score": 42,
                "risk_level": "moderado",
                "top_risk_factors": "",
                "recommended_action": "Acompanhar evolução.",
            },
            {
                "incident_id": "INC-HIGH",
                "scored_at": scored_at,
                "model_version": "risk-ann-v1-20260820",
                "breach_probability": 0.70,
                "risk_score": 68,
                "risk_level": "alto",
                "top_risk_factors": "pressão operacional",
                "recommended_action": ("Priorizar investigação preventiva."),
            },
            {
                "incident_id": "INC-CRITICAL",
                "scored_at": scored_at,
                "model_version": "risk-ann-v1-20260820",
                "breach_probability": 0.91,
                "risk_score": 92,
                "risk_level": "crítico",
                "top_risk_factors": "prioridade alta",
                "recommended_action": ("Priorizar atendimento imediatamente."),
            },
        ]
    )


def test_only_high_and_critical_are_published() -> None:
    publisher = MagicMock()

    count = publish_risk_alerts(
        _scores(),
        publisher,
    )

    assert count == 2
    assert publisher.publish.call_count == 2

    published_events = [call.args[0] for call in publisher.publish.call_args_list]

    assert {event.incident_id for event in published_events} == {
        "INC-HIGH",
        "INC-CRITICAL",
    }


def test_empty_scores_publish_nothing() -> None:
    publisher = MagicMock()

    scores = _scores().iloc[0:0]

    count = publish_risk_alerts(
        scores,
        publisher,
    )

    assert count == 0
    publisher.publish.assert_not_called()
