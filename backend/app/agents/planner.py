"""Planner agent.

Turns a user question into a structured :class:`ResearchPlan`. The plan
may only use explicitly allowed research capabilities (an allow-list).
"""

from __future__ import annotations

from typing import Any

from backend.app.agents import llm
from backend.app.models.schemas import (
    ResearchCapability,
    ResearchPlan,
    ResearchTask,
)
from backend.app.observability.logging import get_logger

logger = get_logger("researchpilot.planner")

_ALLOWED = ", ".join(c.value for c in ResearchCapability)

SYSTEM_PROMPT = f"""You are the Planner agent in a research assistant.
Break the user's question into 3-5 concrete research tasks.

Each task MUST use exactly one of these allowed capabilities: {_ALLOWED}.
- search_sources: search demo web-style sources for a topic
- search_documents: search the local knowledge base of markdown documents
- get_source: retrieve one known source by id (use rarely)

Prefer search_sources and search_documents. Write a short, specific query
for each task. Do not invent capabilities outside the allowed list.
Return a clear objective describing what a good answer must cover."""


def _fallback_plan(question: str) -> ResearchPlan:
    """Deterministic fallback plan if the LLM plan is empty/invalid."""

    return ResearchPlan(
        objective=f"Investigate: {question.strip()[:200]}",
        tasks=[
            ResearchTask(
                description="Find relevant demo sources",
                capability=ResearchCapability.search_sources,
                query=question.strip()[:200],
            ),
            ResearchTask(
                description="Search the local knowledge base",
                capability=ResearchCapability.search_documents,
                query=question.strip()[:200],
            ),
        ],
    )


def _sanitize(plan: ResearchPlan, question: str) -> ResearchPlan:
    """Drop tasks using disallowed capabilities; ensure at least one task."""

    valid = [t for t in plan.tasks if isinstance(t.capability, ResearchCapability)]
    if not valid:
        logger.warning(
            "plan_sanitized", reason="no_valid_tasks", dropped=len(plan.tasks)
        )
        return _fallback_plan(question)
    if len(valid) < len(plan.tasks):
        logger.warning(
            "plan_sanitized",
            reason="disallowed_capability",
            dropped=len(plan.tasks) - len(valid),
        )
    return ResearchPlan(objective=plan.objective or question, tasks=valid[:5])


async def plan_research(
    question: str, *, config: dict[str, Any] | None = None
) -> ResearchPlan:
    """Produce a validated, capability-constrained research plan."""

    plan = await llm.structured_completion(
        ResearchPlan,
        system=SYSTEM_PROMPT,
        user=f"Research question:\n{question}",
        agent_name="planner",
        config=config,
    )
    return _sanitize(plan, question)
