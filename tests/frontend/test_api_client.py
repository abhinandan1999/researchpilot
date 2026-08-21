"""Tests for the frontend API client (mocked HTTP, no backend needed)."""

from __future__ import annotations

import httpx
import pytest

from frontend import api_client
from frontend.api_client import ApiClient


def _install_mock(monkeypatch, handler):
    real_client = httpx.Client

    def factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real_client(*args, **kwargs)

    monkeypatch.setattr(api_client.httpx, "Client", factory)


def test_health(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/health"
        return httpx.Response(200, json={"status": "ok"})

    _install_mock(monkeypatch, handler)
    assert ApiClient().health()["status"] == "ok"


def test_research_success(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/research"
        assert request.headers["X-Session-ID"] == "sess_1"
        return httpx.Response(
            200,
            headers={
                "X-Request-ID": "req_1",
                "X-Trace-ID": "trace_1",
                "X-Session-ID": "sess_1",
            },
            json={
                "request_id": "req_1",
                "trace_id": "trace_1",
                "session_id": "sess_1",
                "status": "completed",
                "report": {"summary": "s", "key_findings": [], "analysis": "", "sources": [], "confidence": 0.8},
            },
        )

    _install_mock(monkeypatch, handler)
    result = ApiClient().research("q", session_id="sess_1")
    assert result.ok
    assert result.request_id == "req_1"
    assert result.trace_id == "trace_1"
    assert result.data["report"]["summary"] == "s"


def test_research_error(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            502, json={"error": "upstream", "error_type": "LLMError"}
        )

    _install_mock(monkeypatch, handler)
    result = ApiClient().research("q", session_id="sess_x")
    assert not result.ok
    assert result.status_code == 502
    assert result.error == "upstream"


def test_send_feedback(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/feedback"
        return httpx.Response(200, json={"status": "recorded"})

    _install_mock(monkeypatch, handler)
    assert ApiClient().send_feedback("req_1", True) is True


def test_is_backend_up_false(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no backend")

    _install_mock(monkeypatch, handler)
    assert ApiClient().is_backend_up() is False
