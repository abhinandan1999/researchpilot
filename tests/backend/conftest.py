"""Shared pytest fixtures for backend tests.

The LLM is faked here so no OpenAI (or Langfuse) access is required.
"""

from __future__ import annotations

import pytest

from backend.app.agents import llm as llm_module
from backend.app.config import DemoScenario, settings
from backend.app.models.schemas import (
    FactCheckResult,
    ResearchCapability,
    ResearchPlan,
    ResearchReport,
    ResearchTask,
)
from backend.app.observability.metrics import metrics


def _fake_plan(user: str) -> ResearchPlan:
    query = user.replace("Research question:", "").strip()[:120] or "AI agents"
    return ResearchPlan(
        objective=f"Investigate: {query}",
        tasks=[
            ResearchTask(
                description="Search demo sources",
                capability=ResearchCapability.search_sources,
                query=query,
            ),
            ResearchTask(
                description="Search local docs",
                capability=ResearchCapability.search_documents,
                query=query,
            ),
        ],
    )


async def _fake_structured_completion(schema, *, system, user, agent_name, config=None, temperature=0.2):
    """Deterministic stand-in for the real LLM call."""

    if schema is ResearchPlan:
        return _fake_plan(user)
    if schema is FactCheckResult:
        return FactCheckResult(
            supported_claims=["Reliable agents constrain the tool action space"],
            unsupported_claims=[],
            missing_evidence=[],
            sufficient_evidence=True,
        )
    if schema is ResearchReport:
        return ResearchReport(
            summary="A concise, grounded summary of the findings.",
            key_findings=["Constrain tools", "Cap loops", "Instrument everything"],
            analysis="Detailed synthesis of the collected evidence.",
            sources=[],
            confidence=0.8,
        )
    raise AssertionError(f"Unexpected schema in fake LLM: {schema}")


@pytest.fixture(autouse=True)
def fake_llm(monkeypatch):
    """Patch the shared structured_completion for all agents."""

    monkeypatch.setattr(
        llm_module, "structured_completion", _fake_structured_completion
    )


@pytest.fixture(autouse=True)
def reset_environment():
    """Reset demo scenario, timeouts, and metrics between tests."""

    original_scenario = settings.demo_scenario
    original_mode = settings.demo_mode
    original_timeout = settings.tool_timeout_seconds
    settings.demo_scenario = DemoScenario.normal
    settings.demo_mode = True
    metrics.reset()
    yield
    settings.demo_scenario = original_scenario
    settings.demo_mode = original_mode
    settings.tool_timeout_seconds = original_timeout
    metrics.reset()
