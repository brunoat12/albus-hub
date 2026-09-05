from __future__ import annotations

import time
from datetime import UTC, datetime

import pika

from albus_hub.alerts.consumer import RabbitMQRiskAlertConsumer
from albus_hub.alerts.publisher import RabbitMQRiskAlertPublisher
from albus_hub.alerts.risk_events import RiskAlertEvent
from albus_hub.config import get_settings


def main() -> None:
    settings = get_settings()

    rabbitmq_url = settings.rabbitmq_url
    queue_name = settings.rabbitmq_queue

    print("=== RABBITMQ RISK ALERT E2E ===")
    print(f"Queue: {queue_name}")

    parameters = pika.URLParameters(
        rabbitmq_url
    )

    connection = pika.BlockingConnection(
        parameters
    )

    channel = connection.channel()

    try:
        channel.queue_declare(
            queue=queue_name,
            durable=True,
        )

        # Ambiente local de teste:
        # remove mensagens antigas antes do E2E.
        channel.queue_purge(
            queue=queue_name,
        )

        event = RiskAlertEvent(
            incident_id="INC-E2E-RABBITMQ",
            scored_at=datetime.now(UTC),
            model_version="risk-ann-v1-20260820",
            breach_probability=0.91,
            risk_score=92,
            risk_level="crítico",
            top_risk_factors=(
                "prioridade alta; "
                "pressão operacional"
            ),
            recommended_action=(
                "Priorizar atendimento e avaliar "
                "escalonamento imediato."
            ),
        )

        publisher = RabbitMQRiskAlertPublisher(
            rabbitmq_url=rabbitmq_url,
            queue_name=queue_name,
        )

        print()
        print("Publicando alerta...")

        publisher.publish(
            event
        )

        print(
            "RABBITMQ_ALERT_PUBLISH=SUCCESS"
        )

        method = None
        properties = None
        body = None

        for _ in range(20):
            method, properties, body = (
                channel.basic_get(
                    queue=queue_name,
                    auto_ack=False,
                )
            )

            if method is not None:
                break

            time.sleep(0.25)

        if (
            method is None
            or body is None
        ):
            raise RuntimeError(
                "Mensagem não encontrada "
                "na fila após publicação."
            )

        consumed: list[RiskAlertEvent] = []

        consumer = RabbitMQRiskAlertConsumer(
            rabbitmq_url=rabbitmq_url,
            queue_name=queue_name,
            handler=consumed.append,
        )

        print("Consumindo alerta...")

        consumer._on_message(
            channel,
            method,
            properties,
            body,
        )

        if len(consumed) != 1:
            raise RuntimeError(
                "Consumer não processou "
                "exatamente um alerta."
            )

        received = consumed[0]

        if (
            received.incident_id
            != event.incident_id
        ):
            raise RuntimeError(
                "incident_id recebido "
                "diverge do publicado."
            )

        queue_state = channel.queue_declare(
            queue=queue_name,
            durable=True,
            passive=True,
        )

        if (
            queue_state.method.message_count
            != 0
        ):
            raise RuntimeError(
                "Fila não ficou vazia "
                "após ACK."
            )

        print(
            "RABBITMQ_ALERT_CONSUME=SUCCESS"
        )
        print(
            "Incident:",
            received.incident_id,
        )
        print(
            "Risk level:",
            received.risk_level,
        )
        print(
            "Risk score:",
            received.risk_score,
        )

        print()
        print(
            "RABBITMQ_ALERT_E2E=SUCCESS"
        )

    finally:
        if connection.is_open:
            connection.close()


if __name__ == "__main__":
    main()
