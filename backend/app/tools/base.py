"""Base helpers for observable, bounded, retryable tool execution.

Every tool call is:
- executed under a real timeout via :func:`asyncio.wait_for`;
- logged (start / completion / failure / timeout) with duration;
- counted in the in-process metrics collector;
- wrapped in a Langfuse span (no-op when Langfuse is disabled).
"""

from __future__ import annotations

import asyncio
from typing import Awaitable, Callable, TypeVar

from backend.app.config import settings
from backend.app.observability import langfuse
from backend.app.observability.logging import get_logger
from backend.app.observability.metrics import metrics
from backend.app.utils.errors import ResearchPilotError, ToolError, ToolTimeoutError
from backend.app.utils.time import elapsed_ms, monotonic_ms

logger = get_logger("researchpilot.tools")

T = TypeVar("T")


async def guarded_tool_call(
    name: str,
    func: Callable[[], Awaitable[T]],
    *,
    timeout: float | None = None,
    **span_attrs: object,
) -> T:
    """Run ``func`` as an observable, bounded tool call."""

    timeout = settings.tool_timeout_seconds if timeout is None else timeout
    metrics.incr("tool_calls")
    start = monotonic_ms()
    logger.info("tool_started", tool=name, timeout_s=timeout, **span_attrs)

    with langfuse.tool_span(f"tool:{name}", tool=name, **span_attrs):
        try:
            result = await asyncio.wait_for(func(), timeout=timeout)
        except asyncio.TimeoutError as exc:
            metrics.incr("tool_failures")
            metrics.incr("tool_timeouts")
            duration = elapsed_ms(start)
            logger.error(
                "tool_timeout",
                tool=name,
                duration_ms=duration,
                timeout_s=timeout,
                status="timeout",
                error_type="ToolTimeoutError",
            )
            raise ToolTimeoutError(
                f"Tool '{name}' timed out after {timeout}s"
            ) from exc
        except ResearchPilotError as exc:
            metrics.incr("tool_failures")
            logger.error(
                "tool_failed",
                tool=name,
                duration_ms=elapsed_ms(start),
                status="failed",
                error_type=exc.error_type,
                error=exc.message,
            )
            raise
        except Exception as exc:  # unexpected -> wrap as ToolError
            metrics.incr("tool_failures")
            logger.error(
                "tool_failed",
                tool=name,
                duration_ms=elapsed_ms(start),
                status="failed",
                error_type=type(exc).__name__,
                error=str(exc),
            )
            raise ToolError(f"Tool '{name}' failed: {exc}") from exc

    logger.info(
        "tool_completed",
        tool=name,
        duration_ms=elapsed_ms(start),
        status="ok",
    )
    return result


async def with_retries(
    name: str,
    factory: Callable[[int], Awaitable[T]],
    *,
    max_retries: int | None = None,
) -> T:
    """Execute ``factory(attempt)`` with bounded retries on transient errors.

    ``factory`` receives the 1-based attempt number. Only
    :class:`ResearchPilotError` instances marked ``retryable`` are retried.
    """

    max_retries = settings.max_retries if max_retries is None else max_retries
    attempt = 0
    last_exc: Exception | None = None

    while attempt <= max_retries:
        attempt += 1
        try:
            return await factory(attempt)
        except ResearchPilotError as exc:
            last_exc = exc
            if not exc.retryable or attempt > max_retries:
                raise
            metrics.incr("retries")
            logger.warning(
                "retry_started",
                tool=name,
                attempt=attempt + 1,
                max_retries=max_retries,
                error_type=exc.error_type,
            )

    assert last_exc is not None  # pragma: no cover
    raise last_exc
