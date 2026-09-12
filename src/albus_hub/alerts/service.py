from __future__ import annotations

from typing import Protocol

import pandas as pd

from albus_hub.alerts.risk_events import (
    build_risk_alert_event,
    is_alert_eligible,
)


class RiskAlertPublisher(Protocol):
    def publish(self, event) -> None: ...


def publish_risk_alerts(
    scores: pd.DataFrame,
    publisher: RiskAlertPublisher,
) -> int:
    """Publica alertas apenas para scores alto ou crítico."""
    published = 0

    for row in scores.to_dict(orient="records"):
        if not is_alert_eligible(str(row["risk_level"])):
            continue

        event = build_risk_alert_event(row)

        publisher.publish(event)

        published += 1

    return published
