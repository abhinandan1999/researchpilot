"""Tests for local tools and demo scenarios."""

from __future__ import annotations

import time

import pytest

from backend.app.config import DemoScenario, settings
from backend.app.models.schemas import DocumentSearchResult, SearchResult, Source
from backend.app.observability.metrics import metrics
from backend.app.tools.documents import search_documents
from backend.app.tools.search import search_sources
from backend.app.tools.sources import get_source
from backend.app.utils.errors import ToolError, ToolTimeoutError, ValidationError


async def test_search_sources_normal():
    result = await search_sources("reliable AI agents")
    assert isinstance(result, SearchResult)
    assert result.sources
    assert all(isinstance(s, Source) and s.is_demo for s in result.sources)


async def test_search_documents_normal():
    result = await search_documents("agent memory retrieval")
    assert isinstance(result, DocumentSearchResult)
    assert result.passages


async def test_get_source_valid():
    src = await get_source("src-agents-001")
    assert src.source_id == "src-agents-001"


async def test_get_source_invalid():
    with pytest.raises(ValidationError):
        await get_source("does-not-exist")


async def test_search_empty_query():
    with pytest.raises(ToolError):
        await search_sources("   ")


async def test_scenario_search_failure():
    settings.demo_scenario = DemoScenario.search_failure
    with pytest.raises(ToolError):
        await search_sources("agents")
    assert metrics.snapshot()["tools"]["failures"] >= 1


async def test_scenario_search_retry_recovers():
    settings.demo_scenario = DemoScenario.search_retry
    result = await search_sources("agents")  # first attempt fails, retry succeeds
    assert result.sources
    assert metrics.snapshot()["retries"] >= 1


async def test_scenario_slow_search_times_out_quickly():
    settings.demo_scenario = DemoScenario.slow_search
    settings.tool_timeout_seconds = 0.2

    start = time.monotonic()
    with pytest.raises(ToolTimeoutError):
        await search_sources("agents")
    elapsed = time.monotonic() - start

    # Proves the slow (5s) operation was interrupted, not awaited to completion.
    assert elapsed < 3.0
    assert metrics.snapshot()["tools"]["timeouts"] >= 1
