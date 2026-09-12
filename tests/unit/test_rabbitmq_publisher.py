import json
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from albus_hub.alerts.publisher import (
    RabbitMQRiskAlertPublisher,
)
from albus_hub.alerts.risk_events import (
    RiskAlertEvent,
)


def _event() -> RiskAlertEvent:
    return RiskAlertEvent(
        incident_id="INC1234567",
        scored_at=datetime(
            2026,
            9,
            4,
            20,
            30,
            tzinfo=UTC,
        ),
        model_version="risk-ann-v1-20260820",
        breach_probability=0.82,
        risk_score=87,
        risk_level="crítico",
        top_risk_factors="prioridade alta",
        recommended_action=("Priorizar atendimento e avaliar escalonamento imediato."),
    )


def test_empty_url_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="rabbitmq_url",
    ):
        RabbitMQRiskAlertPublisher(
            rabbitmq_url=" ",
            queue_name="albus_alerts",
        )


def test_empty_queue_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="queue_name",
    ):
        RabbitMQRiskAlertPublisher(
            rabbitmq_url="amqp://localhost/",
            queue_name=" ",
        )


@patch("albus_hub.alerts.publisher.pika.BlockingConnection")
@patch("albus_hub.alerts.publisher.pika.URLParameters")
def test_publish_risk_alert(
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

    publisher = RabbitMQRiskAlertPublisher(
        rabbitmq_url=("amqp://albus:albus_local@localhost:5672/"),
        queue_name="albus_alerts",
    )

    publisher.publish(_event())

    url_parameters_mock.assert_called_once_with("amqp://albus:albus_local@localhost:5672/")

    blocking_connection_mock.assert_called_once_with(parameters)

    channel.queue_declare.assert_called_once_with(
        queue="albus_alerts",
        durable=True,
    )

    call = channel.basic_publish.call_args

    assert call.kwargs["exchange"] == ""
    assert call.kwargs["routing_key"] == ("albus_alerts")

    payload = json.loads(call.kwargs["body"].decode("utf-8"))

    assert payload["event_type"] == ("ola_risk_alert")
    assert payload["incident_id"] == ("INC1234567")
    assert payload["risk_level"] == "crítico"

    properties = call.kwargs["properties"]

    assert properties.content_type == ("application/json")
    assert properties.delivery_mode == 2
    assert properties.type == ("ola_risk_alert")

    connection.close.assert_called_once_with()


@patch("albus_hub.alerts.publisher.pika.BlockingConnection")
def test_connection_is_closed_on_failure(
    blocking_connection_mock: MagicMock,
) -> None:
    connection = MagicMock()
    connection.is_open = True

    channel = MagicMock()
    channel.basic_publish.side_effect = RuntimeError("publish failure")

    connection.channel.return_value = channel
    blocking_connection_mock.return_value = connection

    publisher = RabbitMQRiskAlertPublisher(
        rabbitmq_url="amqp://localhost/",
        queue_name="albus_alerts",
    )

    with pytest.raises(
        RuntimeError,
        match="publish failure",
    ):
        publisher.publish(_event())

    connection.close.assert_called_once_with()
