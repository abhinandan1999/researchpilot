"""Lightweight, concurrency-safe in-process metrics collector.

This is a *workshop-local* metrics collector — NOT a distributed
production metrics backend (no Prometheus/Grafana). It aggregates
counters and latency samples in memory, guarded by a lock so it is safe
under concurrent async access.
"""

from __future__ import annotations

import threading
from collections import defaultdict
from contextvars import ContextVar
from typing import Any

_MAX_LATENCY_SAMPLES = 2000

# Per-request counters (isolated per async task via contextvars). This lets
# the observability summary report tokens/tool/LLM counts for a single
# request without racing against other concurrent requests.
_request_counters: ContextVar[dict[str, int] | None] = ContextVar(
    "request_counters", default=None
)


def start_request_metrics() -> dict[str, int]:
    """Begin a fresh per-request counter set and install it in context."""

    counters: dict[str, int] = defaultdict(int)
    _request_counters.set(counters)
    return counters


def get_request_metrics() -> dict[str, int]:
    """Return the current per-request counters (empty if none started)."""

    counters = _request_counters.get()
    return dict(counters) if counters else {}


class MetricsCollector:
    """Thread-safe in-memory counters and latency samples."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: dict[str, int] = defaultdict(int)
        self._latencies_ms: list[float] = []

    # -- mutation -----------------------------------------------------------
    def incr(self, name: str, amount: int = 1) -> None:
        with self._lock:
            self._counters[name] += amount
        request_counters = _request_counters.get()
        if request_counters is not None:
            request_counters[name] += amount

    def observe_latency(self, value_ms: float) -> None:
        with self._lock:
            self._latencies_ms.append(value_ms)
            if len(self._latencies_ms) > _MAX_LATENCY_SAMPLES:
                # keep only the most recent samples
                self._latencies_ms = self._latencies_ms[-_MAX_LATENCY_SAMPLES:]

    def reset(self) -> None:
        with self._lock:
            self._counters.clear()
            self._latencies_ms.clear()

    # -- read ---------------------------------------------------------------
    def _percentile(self, samples: list[float], pct: float) -> float:
        if not samples:
            return 0.0
        ordered = sorted(samples)
        k = max(0, min(len(ordered) - 1, int(round((pct / 100.0) * (len(ordered) - 1)))))
        return round(ordered[k], 2)

    def snapshot(self) -> dict[str, Any]:
        """Return a JSON-serializable snapshot of all metrics."""

        with self._lock:
            c = dict(self._counters)
            latencies = list(self._latencies_ms)

        avg = round(sum(latencies) / len(latencies), 2) if latencies else 0.0
        return {
            "requests": {
                "total": c.get("requests_total", 0),
                "success": c.get("requests_success", 0),
                "failed": c.get("requests_failed", 0),
            },
            "latency": {
                "avg_ms": avg,
                "p95_ms": self._percentile(latencies, 95),
                "samples": len(latencies),
            },
            "agents": {
                "runs": c.get("agent_runs", 0),
                "failures": c.get("agent_failures", 0),
            },
            "subagents": {
                "runs": c.get("subagent_runs", 0),
                "failures": c.get("subagent_failures", 0),
                "parallel_dispatches": c.get("parallel_dispatches", 0),
                "parallel_subagent_runs": c.get("parallel_subagent_runs", 0),
            },
            "tools": {
                "calls": c.get("tool_calls", 0),
                "failures": c.get("tool_failures", 0),
                "timeouts": c.get("tool_timeouts", 0),
            },
            "retries": c.get("retries", 0),
            "llm": {
                "calls": c.get("llm_calls", 0),
                "input_tokens": c.get("input_tokens", 0),
                "output_tokens": c.get("output_tokens", 0),
            },
        }


#: Module-level singleton. This is a metrics *sink*, not request state, so
#: a shared instance is appropriate and its mutation is lock-guarded.
metrics = MetricsCollector()
