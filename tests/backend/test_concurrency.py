"""Concurrency tests proving request context isolation."""

from __future__ import annotations

import asyncio

from backend.app.observability.context import (
    RequestContext,
    get_context,
    reset_context,
    set_context,
)
from backend.app.services.research import run_research


async def test_context_does_not_leak_between_tasks():
    async def task(name: str) -> str:
        token = set_context(
            RequestContext(
                request_id=f"req_{name}",
                trace_id=f"trace_{name}",
                session_id=f"sess_{name}",
            )
        )
        # Yield control so tasks interleave.
        await asyncio.sleep(0)
        observed = get_context().session_id
        reset_context(token)
        return observed

    results = await asyncio.gather(task("A"), task("B"), task("C"))
    assert results == ["sess_A", "sess_B", "sess_C"]


async def test_concurrent_research_requests_isolated():
    async def do(user: str):
        return await run_research(
            question=f"Question from {user}",
            request_id=f"req_{user}",
            trace_id=f"trace_{user}",
            session_id=f"sess_{user}",
        )

    a, b = await asyncio.gather(do("A"), do("B"))

    assert a.session_id == "sess_A" and a.trace_id == "trace_A"
    assert b.session_id == "sess_B" and b.trace_id == "trace_B"
    assert a.request_id != b.request_id
    # Each request produced its own observability numbers.
    assert a.observability.agent_count >= 3
    assert b.observability.agent_count >= 3
