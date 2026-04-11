import os
import sys
import logging
import structlog
from typing import Any, Dict


def scrubber(_, __, event_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Redacts sensitive information from log events."""
    SENSITIVE_KEYS = {
        "password",
        "token",
        "auth_token",
        "api_key",
        "secret",
        "credentials",
    }
    for key in event_dict:
        if any(sk in key.lower() for sk in SENSITIVE_KEYS):
            event_dict[key] = "[REDACTED]"
    return event_dict


def setup_logging(service_name: str, level: int = logging.INFO):
    """
    Configures structured logging for the service using the Standard Library bridge.
    Environment variable ENV=production toggles JSON output.
    """
    is_production = os.getenv("ENV", "production") == "production"

    # 1. Standard Library Configuration
    # Ensures that standard logging (like Uvicorn) also goes to stdout through structlog
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=level,
        force=True,  # Ensure we override any existing config
    )

    # 2. Define Processors
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        scrubber,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if is_production:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=True))

    # 3. Configure structlog with the stdlib bridge
    structlog.configure(
        processors=processors,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # 4. Silence/Configure third-party loggers
    for logger_name in [
        "urllib3",
        "influxdb_client",
        "apscheduler",
        "httpx",
        "sqlalchemy.engine",
        "uvicorn",
        "uvicorn.access",
        "uvicorn.error",
        "uvicorn.asgi",
    ]:
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.WARNING)
        logger.propagate = False
        # Remove any existing handlers to avoid duplicate logs (stdout handled by basicConfig)
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)

    # Explicitly set the levels for uvicorn loggers again to be absolutely sure
    # Some libraries re-initialize logging, so we force it.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.WARNING)

    return structlog.get_logger(service_name)
