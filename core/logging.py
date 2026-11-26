import logging
import sys

import structlog

from core.config import settings


def configure_logging() -> None:
    log_level = getattr(
        logging,
        settings.LOG_LEVEL.upper(),
        None,
    )

    if not isinstance(log_level, int):
        raise ValueError(f"Invalid log level: {settings.LOG_LEVEL}")

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(
            fmt="iso",
            utc=True,
        ),
    ]

    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    handler.setLevel(log_level)
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level)

    for logger_name in (
        "uvicorn",
        "uvicorn.error",
        "gunicorn.error",
    ):
        server_logger = logging.getLogger(logger_name)

        server_logger.handlers.clear()
        server_logger.propagate = True
        server_logger.setLevel(log_level)

    for logger_name in (
        "uvicorn.access",
        "gunicorn.access",
    ):
        access_logger = logging.getLogger(logger_name)

        access_logger.handlers.clear()
        access_logger.propagate = False
        access_logger.disabled = True
