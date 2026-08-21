"""The ``search_sources`` tool with deterministic demo scenarios.

Searches the in-memory demo sources. Supports workshop demo scenarios
(slow_search, search_failure, search_retry) that produce *deterministic*
failures — never random.
"""

from __future__ import annotations

import asyncio

from backend.app.config import DemoScenario, settings
from backend.app.models.schemas import SearchResult, Source
from backend.app.tools.base import guarded_tool_call, with_retries
from backend.app.tools.sources import load_all_sources
from backend.app.utils.errors import ToolError


def _score(query: str, source: Source) -> float:
    """Simple lexical relevance score in [0, 1]."""

    terms = {t for t in query.lower().split() if len(t) > 2}
    if not terms:
        return 0.3
    haystack = f"{source.title} {source.topic} {source.snippet}".lower()
    hits = sum(1 for t in terms if t in haystack)
    return min(1.0, round(hits / len(terms), 3))


def _rank(query: str, limit: int = 5) -> list[Source]:
    scored: list[tuple[float, Source]] = []
    for source in load_all_sources():
        relevance = _score(query, source)
        if relevance > 0:
            scored.append((relevance, source.model_copy(update={"relevance": relevance})))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [s for _, s in scored[:limit]]


async def _search_once(query: str, attempt: int) -> SearchResult:
    """Perform a single search attempt, applying the active demo scenario."""

    scenario = settings.demo_scenario if settings.demo_mode else DemoScenario.normal

    if scenario is DemoScenario.slow_search:
        # Intentionally slow: the bounded tool timeout should interrupt this.
        await asyncio.sleep(5.0)
    elif scenario is DemoScenario.search_failure:
        raise ToolError("Demo scenario 'search_failure': source search failed")
    elif scenario is DemoScenario.search_retry and attempt == 1:
        # First attempt fails, subsequent attempts succeed.
        raise ToolError("Demo scenario 'search_retry': transient failure on attempt 1")

    # Small, non-blocking simulated latency for a realistic trace.
    await asyncio.sleep(0.05)
    return SearchResult(query=query, sources=_rank(query))


async def search_sources(query: str) -> SearchResult:
    """Search demo sources for ``query`` and return ranked results.

    Bounded by ``TOOL_TIMEOUT_SECONDS`` and retried (transient failures
    only) up to ``MAX_RETRIES`` times.
    """

    if not isinstance(query, str) or not query.strip():
        raise ToolError("search query must be a non-empty string")

    async def factory(attempt: int) -> SearchResult:
        return await guarded_tool_call(
            "search_sources",
            lambda: _search_once(query, attempt),
            attempt=attempt,
            query_length=len(query),
        )

    return await with_retries("search_sources", factory)
