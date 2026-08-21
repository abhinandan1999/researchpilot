"""Structured JSON logging via :mod:`structlog`.

Every log line is a JSON object containing at least ``timestamp``,
``level``, ``service`` and ``event``. Request context (request_id,
trace_id, session_id, user_id) is automatically merged in when present.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog

from backend.app.config import settings
from backend.app.observability.context import context_as_dict
from backend.app.observability.redaction import redact_mapping

_CONFIGURED = False


def _add_service(_: Any, __: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    event_dict.setdefault("service", settings.service_name)
    event_dict.setdefault("environment", settings.environment)
    return event_dict


def _add_request_context(
    _: Any, __: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    for key, value in context_as_dict().items():
        event_dict.setdefault(key, value)
    return event_dict


def _redact(_: Any, __: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    return redact_mapping(event_dict)


def configure_logging() -> None:
    """Configure structlog + stdlib logging for JSON output (idempotent)."""

    global _CONFIGURED
    if _CONFIGURED:
        return

    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=level,
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True, key="timestamp"),
            _add_service,
            _add_request_context,
            _redact,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    _CONFIGURED = True


def get_logger(name: str = "researchpilot") -> structlog.stdlib.BoundLogger:
    """Return a configured structlog logger."""

    if not _CONFIGURED:
        configure_logging()
    return structlog.get_logger(name)
