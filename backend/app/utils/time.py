"""Time helpers."""

from __future__ import annotations

import time
from datetime import datetime, timezone


def utc_now() -> datetime:
    """Return current timezone-aware UTC time."""

    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    """Return current UTC time as an ISO-8601 string."""

    return utc_now().isoformat()


def monotonic_ms() -> float:
    """Return a monotonic timestamp in milliseconds (for durations)."""

    return time.monotonic() * 1000.0


def elapsed_ms(start_ms: float) -> float:
    """Return elapsed milliseconds since ``start_ms``."""

    return round(monotonic_ms() - start_ms, 2)
