"""Tests for FastAPI endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app.api import routes
from backend.app.main import create_app
from backend.app.utils.errors import LLMError


@pytest.fixture
def client():
    app = create_app()
    with TestClient(app) as c:
        yield c


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_ready(client):
    resp = client.get("/ready")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ready"
    assert "demo_scenario" in body


def test_metrics_endpoint(client):
    resp = client.get("/api/v1/metrics")
    assert resp.status_code == 200
    body = resp.json()
    assert "requests" in body and "tools" in body and "agents" in body


def test_research_flow_and_headers(client):
    resp = client.post(
        "/api/v1/research",
        json={"question": "How do I build reliable AI agents?"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "completed"
    assert body["report"]["summary"]
    assert body["observability"]["agent_count"] >= 3
    # correlation headers echoed back
    assert resp.headers.get("X-Request-ID")
    assert resp.headers.get("X-Trace-ID")
    assert resp.headers.get("X-Session-ID")


def test_research_propagates_supplied_ids(client):
    resp = client.post(
        "/api/v1/research",
        json={"question": "What is agent memory?"},
        headers={"X-Session-ID": "sess_abc", "X-Trace-ID": "trace_abc"},
    )
    assert resp.status_code == 200
    assert resp.headers["X-Session-ID"] == "sess_abc"
    assert resp.headers["X-Trace-ID"] == "trace_abc"
    assert resp.json()["session_id"] == "sess_abc"


def test_get_research_by_id(client):
    resp = client.post(
        "/api/v1/research", json={"question": "What is RAG?"}
    )
    request_id = resp.json()["request_id"]
    fetched = client.get(f"/api/v1/research/{request_id}")
    assert fetched.status_code == 200
    assert fetched.json()["request_id"] == request_id


def test_get_research_not_found(client):
    assert client.get("/api/v1/research/nope").status_code == 404


def test_feedback(client):
    resp = client.post("/api/v1/research", json={"question": "What is RAG?"})
    request_id = resp.json()["request_id"]
    fb = client.post(
        "/api/v1/feedback", json={"request_id": request_id, "thumbs_up": True}
    )
    assert fb.status_code == 200
    assert fb.json()["thumbs_up"] is True


def test_validation_error_returns_422(client):
    resp = client.post("/api/v1/research", json={"question": ""})
    assert resp.status_code == 422


def test_domain_error_returns_mapped_status(client, monkeypatch):
    async def boom(**kwargs):
        raise LLMError("upstream failed")

    monkeypatch.setattr(routes, "run_research", boom)
    resp = client.post("/api/v1/research", json={"question": "trigger error"})
    assert resp.status_code == 502
    body = resp.json()
    assert body["error_type"] == "LLMError"
    assert "request_id" in body
