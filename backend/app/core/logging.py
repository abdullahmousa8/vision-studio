import logging
import sys

import structlog


def setup_logging(level: int = logging.INFO) -> None:
    """Configure structlog with JSON rendering for production, key-value for dev."""
    logging.basicConfig(stream=sys.stdout, level=level, format="%(message)s")

    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.TimeStamper(fmt="iso"),
    ]

    structlog.configure(
        processors=[*processors, structlog.processors.JSONRenderer()],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


setup_logging()


def get_logger(name: str = "app"):
    return structlog.get_logger(name)
