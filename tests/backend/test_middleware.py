"""Tests for request-context middleware."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app


@pytest.fixture
def client():
    app = create_app()
    with TestClient(app) as c:
        yield c


def test_generates_ids_when_absent(client):
    resp = client.get("/health")
    assert resp.headers["X-Request-ID"].startswith("req_")
    assert resp.headers["X-Trace-ID"].startswith("trace_")
    assert resp.headers["X-Session-ID"].startswith("sess_")


def test_propagates_supplied_ids(client):
    resp = client.get(
        "/health",
        headers={
            "X-Request-ID": "req_custom",
            "X-Trace-ID": "trace_custom",
            "X-Session-ID": "sess_custom",
        },
    )
    assert resp.headers["X-Request-ID"] == "req_custom"
    assert resp.headers["X-Trace-ID"] == "trace_custom"
    assert resp.headers["X-Session-ID"] == "sess_custom"
