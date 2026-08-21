"""JSON helpers used across the backend."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def dumps(value: Any) -> str:
    """Serialize ``value`` to a compact, deterministic JSON string."""

    return json.dumps(value, default=str, sort_keys=True, separators=(",", ":"))


def sha256_hash(text: str) -> str:
    """Return a short sha256 hash of ``text`` (used for privacy-safe metadata)."""

    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
