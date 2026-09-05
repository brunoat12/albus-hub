from __future__ import annotations

import pandas as pd

from albus_hub.alerts.publisher import RabbitMQRiskAlertPublisher
from albus_hub.alerts.service import publish_risk_alerts
from albus_hub.config import get_settings


def main() -> None:
    settings = get_settings()

    scores_path = settings.absolute_path(
        settings.locaweb_risk_scores_file
    )

    if not scores_path.exists():
        raise RuntimeError(
            "Arquivo de risk scores não encontrado: "
            f"{scores_path}"
        )

    scores = pd.read_parquet(
        scores_path
    )

    print("=== PUBLICACAO DE ALERTAS DE RISCO ===")
    print("Scores:", len(scores))
    print("Queue:", settings.rabbitmq_queue)

    publisher = RabbitMQRiskAlertPublisher(
        rabbitmq_url=settings.rabbitmq_url,
        queue_name=settings.rabbitmq_queue,
    )

    published = publish_risk_alerts(
        scores,
        publisher,
    )

    print()
    print(
        f"RABBITMQ_ALERTS_PUBLISHED={published}"
    )
    print(
        "RABBITMQ_ALERTS=SUCCESS"
    )


if __name__ == "__main__":
    main()
