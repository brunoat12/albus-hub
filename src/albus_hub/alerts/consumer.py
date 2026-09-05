from __future__ import annotations

import json
from collections.abc import Callable

import pika
from pydantic import ValidationError

from albus_hub.alerts.risk_events import RiskAlertEvent

RiskAlertHandler = Callable[[RiskAlertEvent], None]


def log_risk_alert(
    event: RiskAlertEvent,
) -> None:
    """Handler padrão: registra o alerta consumido."""
    print(
        "RISK_ALERT_CONSUMED "
        f"incident_id={event.incident_id} "
        f"risk_level={event.risk_level} "
        f"risk_score={event.risk_score}"
    )


class RabbitMQRiskAlertConsumer:
    """Consome e valida alertas operacionais do RabbitMQ."""

    def __init__(
        self,
        *,
        rabbitmq_url: str,
        queue_name: str,
        handler: RiskAlertHandler = log_risk_alert,
    ) -> None:
        if not rabbitmq_url.strip():
            raise ValueError(
                "rabbitmq_url não pode ser vazio."
            )

        if not queue_name.strip():
            raise ValueError(
                "queue_name não pode ser vazio."
            )

        self.rabbitmq_url = rabbitmq_url
        self.queue_name = queue_name
        self.handler = handler

    def _on_message(
        self,
        channel,
        method,
        _properties,
        body: bytes,
    ) -> None:
        try:
            payload = json.loads(
                body.decode("utf-8")
            )

            event = RiskAlertEvent.model_validate(
                payload
            )

            self.handler(
                event
            )

        except (
            UnicodeDecodeError,
            json.JSONDecodeError,
            ValidationError,
        ):
            channel.basic_nack(
                delivery_tag=method.delivery_tag,
                requeue=False,
            )
            return

        except Exception:
            channel.basic_nack(
                delivery_tag=method.delivery_tag,
                requeue=False,
            )
            raise

        channel.basic_ack(
            delivery_tag=method.delivery_tag
        )

    def start(self) -> None:
        """Inicia o consumo bloqueante da fila configurada."""
        parameters = pika.URLParameters(
            self.rabbitmq_url
        )

        connection = pika.BlockingConnection(
            parameters
        )

        try:
            channel = connection.channel()

            channel.queue_declare(
                queue=self.queue_name,
                durable=True,
            )

            channel.basic_qos(
                prefetch_count=1
            )

            channel.basic_consume(
                queue=self.queue_name,
                on_message_callback=self._on_message,
                auto_ack=False,
            )

            channel.start_consuming()

        finally:
            if connection.is_open:
                connection.close()
