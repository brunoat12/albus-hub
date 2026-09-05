from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

ALERT_EVENT_TYPE = "ola_risk_alert"

AlertRiskLevel = Literal[
    "alto",
    "crítico",
]


class RiskAlertEvent(BaseModel):
    """Contrato do evento de alerta operacional publicado no RabbitMQ."""

    model_config = ConfigDict(
        extra="forbid",
    )

    event_type: Literal["ola_risk_alert"] = ALERT_EVENT_TYPE
    incident_id: str = Field(min_length=1)
    scored_at: datetime
    model_version: str = Field(min_length=1)
    breach_probability: float = Field(
        ge=0.0,
        le=1.0,
    )
    risk_score: int = Field(
        ge=0,
        le=100,
    )
    risk_level: AlertRiskLevel
    top_risk_factors: str = ""
    recommended_action: str = Field(min_length=1)

    def to_message(self) -> dict[str, Any]:
        """Retorna payload JSON-safe para publicação."""
        return self.model_dump(
            mode="json",
        )


def is_alert_eligible(
    risk_level: str,
) -> bool:
    """Somente riscos alto ou crítico geram alerta."""
    return risk_level.strip().lower() in {
        "alto",
        "crítico",
    }


def build_risk_alert_event(
    row: dict[str, Any],
) -> RiskAlertEvent:
    """Converte um score operacional elegível em evento de alerta."""
    if not is_alert_eligible(
        str(row["risk_level"]),
    ):
        raise ValueError(
            "Score não elegível para alerta: "
            f"{row['risk_level']}"
        )

    return RiskAlertEvent(
        incident_id=str(row["incident_id"]),
        scored_at=row["scored_at"],
        model_version=str(row["model_version"]),
        breach_probability=float(
            row["breach_probability"]
        ),
        risk_score=int(row["risk_score"]),
        risk_level=str(row["risk_level"]).strip().lower(),
        top_risk_factors=str(
            row.get(
                "top_risk_factors",
                "",
            )
        ),
        recommended_action=str(
            row["recommended_action"]
        ),
    )
