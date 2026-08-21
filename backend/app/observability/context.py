"""Request-scoped context using :mod:`contextvars`.

Context is isolated per async task, so concurrent requests never leak
identifiers into one another. Never use module-level mutable globals for
request state.
"""

from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass, replace

_EMPTY = "-"


@dataclass(frozen=True)
class RequestContext:
    """Immutable request context propagated through a single request."""

    request_id: str = _EMPTY
    trace_id: str = _EMPTY
    session_id: str = _EMPTY
    user_id: str | None = None


_request_context: ContextVar[RequestContext] = ContextVar(
    "request_context", default=RequestContext()
)


def get_context() -> RequestContext:
    """Return the current request context."""

    return _request_context.get()


def set_context(ctx: RequestContext) -> Token[RequestContext]:
    """Set the current request context, returning a reset token."""

    return _request_context.set(ctx)


def reset_context(token: Token[RequestContext]) -> None:
    """Reset the request context to its previous value."""

    _request_context.reset(token)


def bind_context(**updates: object) -> Token[RequestContext]:
    """Bind additional fields onto the current context.

    Returns a token that can be passed to :func:`reset_context`.
    """

    current = _request_context.get()
    new = replace(current, **updates)  # type: ignore[arg-type]
    return _request_context.set(new)


def context_as_dict() -> dict[str, object]:
    """Return the current context as a logging-friendly dict."""

    ctx = _request_context.get()
    data: dict[str, object] = {
        "request_id": ctx.request_id,
        "trace_id": ctx.trace_id,
        "session_id": ctx.session_id,
    }
    if ctx.user_id:
        data["user_id"] = ctx.user_id
    return data
