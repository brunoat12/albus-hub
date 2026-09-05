import json
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from albus_hub.alerts.consumer import (
    RabbitMQRiskAlertConsumer,
)


def _payload() -> dict:
    return {
        "event_type": "ola_risk_alert",
        "incident_id": "INC1234567",
        "scored_at": datetime(
            2026,
            9,
            4,
            20,
            30,
            tzinfo=UTC,
        ).isoformat(),
        "model_version": "risk-ann-v1-20260820",
        "breach_probability": 0.82,
        "risk_score": 87,
        "risk_level": "crítico",
        "top_risk_factors": "prioridade alta",
        "recommended_action": ("Priorizar atendimento e avaliar escalonamento imediato."),
    }


def test_empty_url_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="rabbitmq_url",
    ):
        RabbitMQRiskAlertConsumer(
            rabbitmq_url=" ",
            queue_name="albus_alerts",
        )


def test_empty_queue_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="queue_name",
    ):
        RabbitMQRiskAlertConsumer(
            rabbitmq_url="amqp://localhost/",
            queue_name=" ",
        )


def test_valid_message_is_acknowledged() -> None:
    handler = MagicMock()

    consumer = RabbitMQRiskAlertConsumer(
        rabbitmq_url="amqp://localhost/",
        queue_name="albus_alerts",
        handler=handler,
    )

    channel = MagicMock()
    method = MagicMock()
    method.delivery_tag = 123

    consumer._on_message(
        channel,
        method,
        None,
        json.dumps(
            _payload(),
            ensure_ascii=False,
        ).encode("utf-8"),
    )

    handler.assert_called_once()

    event = handler.call_args.args[0]

    assert event.incident_id == "INC1234567"
    assert event.risk_level == "crítico"

    channel.basic_ack.assert_called_once_with(delivery_tag=123)

    channel.basic_nack.assert_not_called()


def test_invalid_message_is_rejected() -> None:
    consumer = RabbitMQRiskAlertConsumer(
        rabbitmq_url="amqp://localhost/",
        queue_name="albus_alerts",
    )

    channel = MagicMock()
    method = MagicMock()
    method.delivery_tag = 456

    consumer._on_message(
        channel,
        method,
        None,
        b"{invalid-json",
    )

    channel.basic_nack.assert_called_once_with(
        delivery_tag=456,
        requeue=False,
    )

    channel.basic_ack.assert_not_called()


def test_handler_failure_rejects_message() -> None:
    handler = MagicMock(side_effect=RuntimeError("handler failure"))

    consumer = RabbitMQRiskAlertConsumer(
        rabbitmq_url="amqp://localhost/",
        queue_name="albus_alerts",
        handler=handler,
    )

    channel = MagicMock()
    method = MagicMock()
    method.delivery_tag = 789

    with pytest.raises(
        RuntimeError,
        match="handler failure",
    ):
        consumer._on_message(
            channel,
            method,
            None,
            json.dumps(
                _payload(),
                ensure_ascii=False,
            ).encode("utf-8"),
        )

    channel.basic_nack.assert_called_once_with(
        delivery_tag=789,
        requeue=False,
    )

    channel.basic_ack.assert_not_called()


@patch("albus_hub.alerts.consumer.pika.BlockingConnection")
@patch("albus_hub.alerts.consumer.pika.URLParameters")
def test_start_configures_consumer(
    url_parameters_mock: MagicMock,
    blocking_connection_mock: MagicMock,
) -> None:
    parameters = MagicMock()
    url_parameters_mock.return_value = parameters

    connection = MagicMock()
    connection.is_open = True
    blocking_connection_mock.return_value = connection

    channel = MagicMock()
    connection.channel.return_value = channel

    consumer = RabbitMQRiskAlertConsumer(
        rabbitmq_url="amqp://localhost/",
        queue_name="albus_alerts",
    )

    consumer.start()

    channel.queue_declare.assert_called_once_with(
        queue="albus_alerts",
        durable=True,
    )

    channel.basic_qos.assert_called_once_with(prefetch_count=1)

    channel.basic_consume.assert_called_once_with(
        queue="albus_alerts",
        on_message_callback=consumer._on_message,
        auto_ack=False,
    )

    channel.start_consuming.assert_called_once_with()
    connection.close.assert_called_once_with()
