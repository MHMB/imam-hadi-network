"""Structured logging configured once at process start.

Uses ``structlog`` to emit JSON in prod and a readable console renderer in dev.
Import ``get_logger`` anywhere — never call ``logging.getLogger`` directly.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog

from app.config import settings


def configure_logging() -> None:
    """Set up structlog + stdlib logging.  Idempotent."""
    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)

    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        timestamper,
    ]

    if settings.app_env == "dev":
        renderer: Any = structlog.dev.ConsoleRenderer(colors=True)
    else:
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, settings.log_level)),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )

    # Quiet noisy libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def get_logger(name: str | None = None) -> Any:
    """Get a structlog logger.  ``name`` is conventionally the module path.

    Return type is ``Any`` because structlog returns differently-bound
    proxies depending on configuration; pinning a concrete class fights
    the library.  Call sites use bound methods (``info``, ``warning``, …)
    which structlog dispatches dynamically.
    """
    return structlog.get_logger(name)
