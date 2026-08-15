from __future__ import annotations

import logging
import os

from azure.monitor.opentelemetry import configure_azure_monitor

logger = logging.getLogger("albus_hub")
logger.setLevel(logging.INFO)

_configured = False


def configure_observability() -> bool:
    """Configure Azure Monitor when Application Insights is available."""
    global _configured

    if _configured:
        return True

    if not os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING"):
        return False

    configure_azure_monitor(logger_name="albus_hub")

    _configured = True
    logger.info("Azure Monitor OpenTelemetry configured")

    return True
