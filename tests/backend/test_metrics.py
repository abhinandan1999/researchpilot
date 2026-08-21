"""Tests for the in-process metrics collector."""

from __future__ import annotations

import asyncio

from backend.app.observability.metrics import (
    MetricsCollector,
    get_request_metrics,
    metrics,
    start_request_metrics,
)


def test_snapshot_shape():
    collector = MetricsCollector()
    collector.incr("requests_total", 3)
    collector.incr("tool_calls", 5)
    collector.observe_latency(100)
    collector.observe_latency(300)
    snap = collector.snapshot()
    assert snap["requests"]["total"] == 3
    assert snap["tools"]["calls"] == 5
    assert snap["latency"]["avg_ms"] == 200.0
    assert snap["latency"]["samples"] == 2


def test_percentile_bounds():
    collector = MetricsCollector()
    for v in range(1, 101):
        collector.observe_latency(v)
    snap = collector.snapshot()
    assert 90 <= snap["latency"]["p95_ms"] <= 100


async def test_request_metrics_isolated_per_task():
    async def worker(n: int) -> int:
        start_request_metrics()
        for _ in range(n):
            metrics.incr("llm_calls")
        await asyncio.sleep(0)
        return get_request_metrics().get("llm_calls", 0)

    results = await asyncio.gather(worker(2), worker(5), worker(3))
    assert sorted(results) == [2, 3, 5]
