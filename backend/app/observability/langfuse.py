"""Optional Langfuse integration.

The application runs fully without Langfuse configured. When credentials
are present, one research request maps to one logical Langfuse trace via
the LangChain callback handler, and tools emit nested spans.

All Langfuse access is defensive: missing package or missing credentials
degrade to no-ops so that unit tests never require Langfuse.
"""

from __future__ import annotations

import sys
from contextlib import contextmanager, nullcontext
from typing import Any, Iterator

from backend.app.config import settings
from backend.app.observability.logging import get_logger

logger = get_logger("researchpilot.langfuse")

_client: Any | None = None
_initialized = False


def init_langfuse() -> None:
    """Initialize the Langfuse client once, if configured."""

    global _client, _initialized
    if _initialized:
        return
    _initialized = True

    if not settings.langfuse_configured:
        logger.info("langfuse_disabled", reason="credentials_not_set")
        return

    try:
        from langfuse import Langfuse

        _client = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
        )
        logger.info("langfuse_enabled", host=settings.langfuse_host)
    except Exception as exc:  # pragma: no cover - defensive
        _client = None
        logger.warning("langfuse_init_failed", error=str(exc))


def is_enabled() -> bool:
    return _client is not None


def get_client() -> Any | None:
    return _client


def get_callback_handler() -> Any | None:
    """Return a LangChain callback handler bound to Langfuse, or None."""

    if _client is None:
        return None
    try:
        from langfuse.langchain import CallbackHandler

        return CallbackHandler()
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("langfuse_handler_failed", error=str(exc))
        return None


def build_run_config(
    *,
    run_name: str,
    session_id: str,
    user_id: str | None,
    metadata: dict[str, Any],
    tags: list[str] | None = None,
) -> dict[str, Any]:
    """Build a LangGraph/LangChain run config with Langfuse trace attributes."""

    config: dict[str, Any] = {
        "run_name": run_name,
        "metadata": {
            "langfuse_session_id": session_id,
            **({"langfuse_user_id": user_id} if user_id else {}),
            "langfuse_tags": tags or [],
            **metadata,
        },
    }
    handler = get_callback_handler()
    if handler is not None:
        config["callbacks"] = [handler]
    return config


@contextmanager
def tool_span(name: str, **attributes: Any) -> Iterator[None]:
    """Emit a nested Langfuse span for a tool call (no-op if disabled).

    Only span *setup* is guarded by try/except (defensive: a Langfuse
    outage must never break a tool call). Once the span is live, the
    caller's exception (if any) is left to propagate normally through the
    span's own __exit__ so it's recorded as an error span - catching it
    here and yielding a second time would violate the generator-based
    context manager protocol (a generator may only yield once).
    """

    if _client is None:
        with nullcontext():
            yield
        return

    try:
        span_cm = _client.start_as_current_observation(
            name=name, as_type="tool", metadata=attributes
        )
        span_cm.__enter__()
    except Exception:  # pragma: no cover - defensive, span setup failed
        with nullcontext():
            yield
        return

    try:
        yield
    except BaseException:
        span_cm.__exit__(*sys.exc_info())
        raise
    else:
        span_cm.__exit__(None, None, None)


class _TraceHandle:
    """Best-effort handle for scoring a specific Langfuse trace by id.

    Holds the trace_id itself, not the span object: evaluation happens
    after the graph invocation completes, by which point the span's own
    "current" context has already exited, so scoring must target the
    trace explicitly rather than relying on an active context.
    """

    def __init__(self, trace_id: str | None) -> None:
        self._trace_id = trace_id

    def score(self, name: str, value: float, comment: str | None = None) -> None:
        if self._trace_id is None or _client is None:
            return
        try:
            _client.create_score(
                trace_id=self._trace_id, name=name, value=value, comment=comment
            )
        except Exception:  # pragma: no cover - defensive
            pass


@contextmanager
def research_trace(
    name: str,
    *,
    metadata: dict[str, Any] | None = None,
) -> Iterator[_TraceHandle]:
    """Wrap a research request in a root Langfuse span (no-op if disabled).

    See :func:`tool_span` for why only span *setup* is guarded, not the
    yield itself.
    """

    if _client is None:
        yield _TraceHandle(None)
        return

    try:
        span_cm = _client.start_as_current_observation(
            name=name, as_type="span", metadata=metadata or {}
        )
        span = span_cm.__enter__()
    except Exception:  # pragma: no cover - defensive, span setup failed
        yield _TraceHandle(None)
        return

    try:
        yield _TraceHandle(span.trace_id)
    except BaseException:
        span_cm.__exit__(*sys.exc_info())
        raise
    else:
        span_cm.__exit__(None, None, None)



def flush() -> None:
    """Flush pending Langfuse events (best-effort)."""

    if _client is not None:
        try:
            _client.flush()
        except Exception:  # pragma: no cover - defensive
            pass
