"""Telemetry redaction policy.

Ensures secrets are never logged or sent to external observability
backends, and that user identifiers are pseudonymized.
"""

from __future__ import annotations

from typing import Any

from backend.app.utils.json import sha256_hash

#: Keys whose values must never appear in logs or telemetry.
SECRET_KEYS = frozenset(
    {
        "authorization",
        "api_key",
        "apikey",
        "openai_api_key",
        "langfuse_secret_key",
        "langfuse_public_key",
        "password",
        "secret",
        "token",
        "access_token",
        "x-api-key",
        "cookie",
        "set-cookie",
    }
)

REDACTED = "***redacted***"


def redact_mapping(data: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of ``data`` with secret values redacted."""

    cleaned: dict[str, Any] = {}
    for key, value in data.items():
        if key.lower() in SECRET_KEYS:
            cleaned[key] = REDACTED
        elif isinstance(value, dict):
            cleaned[key] = redact_mapping(value)
        else:
            cleaned[key] = value
    return cleaned


def pseudonymize_user(user_id: str | None) -> str | None:
    """Pseudonymize a user identifier for telemetry.

    A stable hash is returned so that the same user maps to the same
    pseudonym without exposing the raw identifier.
    """

    if not user_id:
        return None
    return f"user_{sha256_hash(user_id)}"


def safe_question_metadata(question: str, *, capture_input: bool) -> dict[str, Any]:
    """Return privacy-aware metadata for a user question.

    When ``capture_input`` is False, the raw question is omitted and only
    safe metadata (length, hash) is returned.
    """

    meta: dict[str, Any] = {
        "question_length": len(question),
        "question_hash": sha256_hash(question),
    }
    if capture_input:
        meta["question"] = question
    return meta
