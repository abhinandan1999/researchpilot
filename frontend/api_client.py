"""HTTP client for the ResearchPilot backend.

This module talks to the FastAPI backend over HTTP only. It never imports
backend implementation code, so the frontend runs independently as long
as the API is reachable.

A synchronous :class:`httpx.Client` is used because it is the safest,
simplest approach inside Streamlit's synchronous execution model.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import httpx

DEFAULT_BASE_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")


@dataclass
class ResearchResult:
    """Parsed research response plus correlation headers."""

    ok: bool
    status_code: int
    data: dict[str, Any]
    request_id: str | None = None
    trace_id: str | None = None
    session_id: str | None = None
    error: str | None = None


class ApiClient:
    """Thin HTTP client for the backend API."""

    def __init__(
        self, base_url: str = DEFAULT_BASE_URL, timeout: float = 120.0
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    # -- system ------------------------------------------------------------
    def health(self) -> dict[str, Any]:
        return self._get_json("/health")

    def ready(self) -> dict[str, Any]:
        return self._get_json("/ready")

    def metrics(self) -> dict[str, Any]:
        return self._get_json("/api/v1/metrics")

    def is_backend_up(self) -> bool:
        try:
            self.health()
            return True
        except Exception:
            return False

    # -- demo scenario -------------------------------------------------------
    def get_demo_scenario(self) -> dict[str, Any]:
        return self._get_json("/api/v1/demo-scenario")

    def set_demo_scenario(self, scenario: str) -> dict[str, Any]:
        with httpx.Client(base_url=self.base_url, timeout=30.0) as client:
            resp = client.post("/api/v1/demo-scenario", json={"scenario": scenario})
            resp.raise_for_status()
            return resp.json()

    # -- research ----------------------------------------------------------
    def research(
        self,
        question: str,
        *,
        session_id: str,
        request_id: str | None = None,
        user_id: str | None = None,
        thumbs_up: bool | None = None,
    ) -> ResearchResult:
        headers = {"X-Session-ID": session_id}
        if request_id:
            headers["X-Request-ID"] = request_id
        if user_id:
            headers["X-User-ID"] = user_id

        body: dict[str, Any] = {"question": question}
        if thumbs_up is not None:
            body["thumbs_up"] = thumbs_up

        try:
            with httpx.Client(base_url=self.base_url, timeout=self.timeout) as client:
                resp = client.post("/api/v1/research", json=body, headers=headers)
        except httpx.HTTPError as exc:
            return ResearchResult(
                ok=False, status_code=0, data={}, error=f"Backend unreachable: {exc}"
            )

        data: dict[str, Any] = {}
        try:
            data = resp.json()
        except Exception:
            data = {}

        return ResearchResult(
            ok=resp.is_success,
            status_code=resp.status_code,
            data=data,
            request_id=resp.headers.get("X-Request-ID") or data.get("request_id"),
            trace_id=resp.headers.get("X-Trace-ID") or data.get("trace_id"),
            session_id=resp.headers.get("X-Session-ID") or data.get("session_id"),
            error=None if resp.is_success else data.get("error", resp.text),
        )

    def send_feedback(self, request_id: str, thumbs_up: bool) -> bool:
        try:
            with httpx.Client(base_url=self.base_url, timeout=30.0) as client:
                resp = client.post(
                    "/api/v1/feedback",
                    json={"request_id": request_id, "thumbs_up": thumbs_up},
                )
            return resp.is_success
        except httpx.HTTPError:
            return False

    # -- internal ----------------------------------------------------------
    def _get_json(self, path: str) -> dict[str, Any]:
        with httpx.Client(base_url=self.base_url, timeout=30.0) as client:
            resp = client.get(path)
            resp.raise_for_status()
            return resp.json()
