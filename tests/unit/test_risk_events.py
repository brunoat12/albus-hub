from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from albus_hub.alerts.risk_events import (
    ALERT_EVENT_TYPE,
    build_risk_alert_event,
    is_alert_eligible,
)


def _base_row() -> dict:
    return {
        "incident_id": "INC1234567",
        "scored_at": datetime(
            2026,
            9,
            4,
            20,
            30,
            tzinfo=UTC,
        ),
        "model_version": "risk-ann-v1-20260820",
        "breach_probability": 0.82,
        "risk_score": 87,
        "risk_level": "crítico",
        "top_risk_factors": "prioridade alta",
        "recommended_action": ("Priorizar atendimento e avaliar escalonamento imediato."),
    }


@pytest.mark.parametrize(
    ("risk_level", "expected"),
    [
        ("alto", True),
        ("crítico", True),
        ("ALTO", True),
        (" Crítico ", True),
        ("moderado", False),
        ("baixo", False),
    ],
)
def test_is_alert_eligible(
    risk_level: str,
    expected: bool,
) -> None:
    assert is_alert_eligible(risk_level) is expected


def test_build_risk_alert_event() -> None:
    event = build_risk_alert_event(_base_row())

    assert event.event_type == ALERT_EVENT_TYPE
    assert event.incident_id == "INC1234567"
    assert event.model_version == ("risk-ann-v1-20260820")
    assert event.breach_probability == 0.82
    assert event.risk_score == 87
    assert event.risk_level == "crítico"


def test_event_to_message_is_json_safe() -> None:
    event = build_risk_alert_event(_base_row())

    message = event.to_message()

    assert message["event_type"] == ("ola_risk_alert")
    assert message["incident_id"] == ("INC1234567")
    assert isinstance(
        message["scored_at"],
        str,
    )


def test_non_eligible_score_is_rejected() -> None:
    row = _base_row()
    row["risk_level"] = "moderado"

    with pytest.raises(
        ValueError,
        match="não elegível",
    ):
        build_risk_alert_event(row)


def test_invalid_probability_is_rejected() -> None:
    row = _base_row()
    row["breach_probability"] = 1.5

    with pytest.raises(ValidationError):
        build_risk_alert_event(row)


def test_invalid_score_is_rejected() -> None:
    row = _base_row()
    row["risk_score"] = 101

    with pytest.raises(ValidationError):
        build_risk_alert_event(row)
