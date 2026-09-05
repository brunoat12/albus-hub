from __future__ import annotations

from albus_hub.alerts.consumer import RabbitMQRiskAlertConsumer
from albus_hub.config import get_settings


def main() -> None:
    settings = get_settings()

    print("=== CONSUMIDOR DE ALERTAS DE RISCO ===")
    print("Queue:", settings.rabbitmq_queue)
    print("Aguardando alertas...")

    consumer = RabbitMQRiskAlertConsumer(
        rabbitmq_url=settings.rabbitmq_url,
        queue_name=settings.rabbitmq_queue,
    )

    try:
        consumer.start()
    except KeyboardInterrupt:
        print()
        print("RABBITMQ_CONSUMER_STOPPED")


if __name__ == "__main__":
    main()
