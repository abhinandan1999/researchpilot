"""ID generation helpers."""

from __future__ import annotations

import uuid


def new_request_id() -> str:
    """Generate a unique request identifier."""

    return f"req_{uuid.uuid4().hex}"


def new_trace_id() -> str:
    """Generate a unique trace identifier."""

    return f"trace_{uuid.uuid4().hex}"


def new_session_id() -> str:
    """Generate a unique session identifier."""

    return f"sess_{uuid.uuid4().hex}"


def new_id(prefix: str) -> str:
    """Generate a generic prefixed identifier."""

    return f"{prefix}_{uuid.uuid4().hex}"
