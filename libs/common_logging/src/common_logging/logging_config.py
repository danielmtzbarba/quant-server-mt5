import logging
from rich.logging import RichHandler
from rich.console import Console

# Setup rich console for consistent clean output
console = Console()


class TaggingAdapter(logging.LoggerAdapter):
    """Prepends a colored tag to log messages."""

    def process(self, msg, kwargs):
        tag = self.extra.get("tag", "UNKN")
        color = self.extra.get("color", "white")
        # Ensure markup works with Rich
        return f"[bold {color}][{tag:^9}][/] {msg}", kwargs


def setup_logging(
    service_name: str, tag: str = "SERVICE", color: str = "white", level=logging.INFO
):
    """Configures centralized logging with colored tags and exhaustive silence."""
    # Use force=True to ensure we override any internal library configurations
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[
            RichHandler(
                rich_tracebacks=True,
                console=console,
                tracebacks_show_locals=True,
                markup=True,
            )
        ],
        force=True,
    )

    # Silence verbose third party loggers
    for logger_name in [
        "urllib3",
        "influxdb_client",
        "apscheduler",
        "httpx",
        "sqlalchemy.engine",
    ]:
        logging.getLogger(logger_name).setLevel(logging.WARNING)

    # Exhaustive Uvicorn suppression
    for uv_logger_name in [
        "uvicorn",
        "uvicorn.access",
        "uvicorn.error",
        "uvicorn.asgi",
    ]:
        uv_logger = logging.getLogger(uv_logger_name)
        uv_logger.setLevel(logging.WARNING)
        uv_logger.propagate = False
        uv_logger.handlers = []

    base_logger = logging.getLogger(service_name)
    return TaggingAdapter(base_logger, {"tag": tag, "color": color})
