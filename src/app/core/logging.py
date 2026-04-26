import logging
import sys
from typing import Any

from app.core.config import Settings


class FallbackStructuredLogger:
    def __init__(self, name: str) -> None:
        self.logger = logging.getLogger(name)

    def info(self, event: str, **kwargs: Any) -> None:
        self.logger.info("%s %s", event, kwargs)

    def exception(self, event: str, **kwargs: Any) -> None:
        self.logger.exception("%s %s", event, kwargs)


def configure_logging(settings: Settings) -> None:
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
    )

    try:
        import structlog
    except ModuleNotFoundError:
        return

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(ensure_ascii=False),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, settings.log_level.upper(), logging.INFO)),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str):
    try:
        import structlog
    except ModuleNotFoundError:
        return FallbackStructuredLogger(name)

    return structlog.get_logger(name)
