"""Research sub-agents dispatched by the Supervisor.

The supervisor fans work out to two specialist sub-agents that run
concurrently:

- **web_research** — external demo/web-style sources (``search_sources``,
  ``get_source``);
- **kb_research** — the local knowledge base of markdown documents
  (``search_documents``).

Splitting the plan by capability is what makes the workflow genuinely
parallel: each sub-agent owns a disjoint slice of the tasks, so their
tool calls, logs, and traces can be attributed independently.
"""

from __future__ import annotations

import asyncio

from backend.app.agents import researcher
from backend.app.config import DemoScenario, settings
from backend.app.models.schemas import ResearchCapability, ResearchPlan, ResearchTask

#: Capability ownership per sub-agent (disjoint by construction).
WEB_CAPABILITIES = {
    ResearchCapability.search_sources,
    ResearchCapability.get_source,
}
KB_CAPABILITIES = {ResearchCapability.search_documents}

WEB_AGENT = "web_research"
KB_AGENT = "kb_research"


def split_tasks(plan: ResearchPlan) -> dict[str, list[ResearchTask]]:
    """Partition plan tasks into per-sub-agent task lists by capability."""

    web = [t for t in plan.tasks if t.capability in WEB_CAPABILITIES]
    kb = [t for t in plan.tasks if t.capability in KB_CAPABILITIES]
    return {WEB_AGENT: web, KB_AGENT: kb}


async def _maybe_stagger(agent: str) -> None:
    """Add a distinct, deterministic delay so parallelism is observable.

    Only active under the ``parallel_research`` demo scenario. The two
    sub-agents get different delays so their start/complete log lines
    interleave, making concurrent execution visible in the logs and traces.
    """

    scenario = settings.demo_scenario if settings.demo_mode else DemoScenario.normal
    if scenario is not DemoScenario.parallel_research:
        return
    # web is deliberately slower than kb so the faster sub-agent finishes
    # first even though both started together.
    await asyncio.sleep(1.5 if agent == WEB_AGENT else 0.5)


async def run_web_research(
    tasks: list[ResearchTask], *, existing_source_ids: set[str] | None = None
) -> dict:
    """Web/demo-source research sub-agent."""

    await _maybe_stagger(WEB_AGENT)
    return await researcher.execute_tasks(
        tasks, existing_source_ids=existing_source_ids
    )


async def run_kb_research(
    tasks: list[ResearchTask], *, existing_source_ids: set[str] | None = None
) -> dict:
    """Local knowledge-base research sub-agent."""

    await _maybe_stagger(KB_AGENT)
    return await researcher.execute_tasks(
        tasks, existing_source_ids=existing_source_ids
    )
