"""Tests for structured logging, redaction, and privacy."""

from __future__ import annotations

import json

from backend.app.observability.logging import get_logger
from backend.app.observability.redaction import (
    pseudonymize_user,
    redact_mapping,
    safe_question_metadata,
)


def test_logger_emits_json_with_required_fields(capsys):
    logger = get_logger("test")
    logger.info("agent_started", agent="planner")
    out = capsys.readouterr().out.strip().splitlines()[-1]
    record = json.loads(out)
    assert record["event"] == "agent_started"
    assert record["level"] == "info"
    assert record["service"] == "researchpilot-backend"
    assert "timestamp" in record
    assert record["agent"] == "planner"


def test_secrets_are_redacted_in_logs(capsys):
    logger = get_logger("test")
    logger.info("thing", api_key="sk-secret", authorization="Bearer xyz")
    record = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert record["api_key"] == "***redacted***"
    assert record["authorization"] == "***redacted***"


def test_redact_mapping_nested():
    data = {"a": 1, "password": "p", "nested": {"token": "t", "ok": "v"}}
    cleaned = redact_mapping(data)
    assert cleaned["password"] == "***redacted***"
    assert cleaned["nested"]["token"] == "***redacted***"
    assert cleaned["nested"]["ok"] == "v"
    assert cleaned["a"] == 1


def test_pseudonymize_user():
    assert pseudonymize_user(None) is None
    p = pseudonymize_user("alice")
    assert p and p.startswith("user_") and "alice" not in p


def test_safe_question_metadata_respects_capture_flag():
    off = safe_question_metadata("secret question", capture_input=False)
    assert "question" not in off
    assert off["question_length"] == len("secret question")
    assert "question_hash" in off

    on = safe_question_metadata("secret question", capture_input=True)
    assert on["question"] == "secret question"
