"""FastAPI middleware for request context, timing, and structured logging.

Establishes request_id / trace_id / session_id (propagated from headers
or generated), binds them into contextvars so every log line and span is
correlated, times the request, and echoes the identifiers back as
response headers.
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from backend.app.observability.context import (
    RequestContext,
    reset_context,
    set_context,
)
from backend.app.observability.logging import get_logger
from backend.app.utils.ids import new_request_id, new_session_id, new_trace_id
from backend.app.utils.time import elapsed_ms, monotonic_ms

logger = get_logger("researchpilot.http")

REQUEST_ID_HEADER = "X-Request-ID"
TRACE_ID_HEADER = "X-Trace-ID"
SESSION_ID_HEADER = "X-Session-ID"
USER_ID_HEADER = "X-User-ID"


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Populate request context and emit request lifecycle logs."""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get(REQUEST_ID_HEADER) or new_request_id()
        trace_id = request.headers.get(TRACE_ID_HEADER) or new_trace_id()
        session_id = request.headers.get(SESSION_ID_HEADER) or new_session_id()
        user_id = request.headers.get(USER_ID_HEADER)

        ctx = RequestContext(
            request_id=request_id,
            trace_id=trace_id,
            session_id=session_id,
            user_id=user_id,
        )
        token = set_context(ctx)
        start = monotonic_ms()

        logger.info(
            "http_request_started",
            method=request.method,
            path=request.url.path,
        )

        try:
            response = await call_next(request)
        except Exception:
            duration = elapsed_ms(start)
            logger.error(
                "http_request_failed",
                method=request.method,
                path=request.url.path,
                status_code=500,
                duration_ms=duration,
            )
            reset_context(token)
            raise

        duration = elapsed_ms(start)
        response.headers[REQUEST_ID_HEADER] = request_id
        response.headers[TRACE_ID_HEADER] = trace_id
        response.headers[SESSION_ID_HEADER] = session_id

        logger.info(
            "http_request_completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration,
        )
        reset_context(token)
        return response
