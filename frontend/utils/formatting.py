"""Small formatting helpers for the Streamlit UI (no backend imports)."""

from __future__ import annotations

from typing import Any


def format_duration(ms: float | int | None) -> str:
    if not ms:
        return "-"
    ms = float(ms)
    if ms < 1000:
        return f"{ms:.0f} ms"
    return f"{ms / 1000:.2f} s"


def format_confidence(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value * 100:.0f}%"


def format_score(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:.2f}"


def safe_get(data: dict[str, Any], *keys: str, default: Any = None) -> Any:
    current: Any = data
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
        if current is None:
            return default
    return current
