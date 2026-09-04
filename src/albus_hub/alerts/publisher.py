from __future__ import annotations

import json

import pika

from albus_hub.alerts.risk_events import RiskAlertEvent


class RabbitMQRiskAlertPublisher:
    """Publica alertas de risco operacional no RabbitMQ."""

    def __init__(
        self,
        *,
        rabbitmq_url: str,
        queue_name: str,
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

    def publish(
        self,
        event: RiskAlertEvent,
    ) -> None:
        """Publica um evento persistente na fila configurada."""
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

            body = json.dumps(
                event.to_message(),
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")

            properties = pika.BasicProperties(
                content_type="application/json",
                content_encoding="utf-8",
                delivery_mode=2,
                type=event.event_type,
            )

            channel.basic_publish(
                exchange="",
                routing_key=self.queue_name,
                body=body,
                properties=properties,
            )

        finally:
            if connection.is_open:
                connection.close()
