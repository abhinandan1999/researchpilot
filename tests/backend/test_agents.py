"""Tests for individual agents."""

from __future__ import annotations

from backend.app.agents import fact_checker, planner, researcher, subagents, writer
from backend.app.models.schemas import (
    FactCheckResult,
    Finding,
    ResearchCapability,
    ResearchPlan,
    ResearchTask,
    Source,
)


async def test_planner_returns_valid_plan():
    plan = await planner.plan_research("How do I build reliable AI agents?")
    assert isinstance(plan, ResearchPlan)
    assert plan.tasks
    assert all(isinstance(t.capability, ResearchCapability) for t in plan.tasks)


async def test_planner_fallback_on_empty(monkeypatch):
    async def empty_plan(*args, **kwargs):
        return ResearchPlan(objective="", tasks=[])

    monkeypatch.setattr(planner.llm, "structured_completion", empty_plan)
    plan = await planner.plan_research("Question about agents")
    assert plan.tasks  # fallback provides tasks


async def test_researcher_collects_sources():
    plan = ResearchPlan(
        objective="obj",
        tasks=[
            {
                "description": "d",
                "capability": ResearchCapability.search_sources,
                "query": "reliable AI agents",
            }
        ],
    )
    result = await researcher.execute_plan(plan)
    assert result["collected_sources"]
    assert result["findings"]
    assert result["errors"] == []


def test_supervisor_splits_tasks_by_capability():
    plan = ResearchPlan(
        objective="obj",
        tasks=[
            ResearchTask(
                description="web",
                capability=ResearchCapability.search_sources,
                query="reliable AI agents",
            ),
            ResearchTask(
                description="kb",
                capability=ResearchCapability.search_documents,
                query="agent observability",
            ),
        ],
    )
    split = subagents.split_tasks(plan)
    assert [t.capability for t in split[subagents.WEB_AGENT]] == [
        ResearchCapability.search_sources
    ]
    assert [t.capability for t in split[subagents.KB_AGENT]] == [
        ResearchCapability.search_documents
    ]


async def test_subagents_use_disjoint_capabilities():
    web_task = ResearchTask(
        description="web",
        capability=ResearchCapability.search_sources,
        query="reliable AI agents",
    )
    kb_task = ResearchTask(
        description="kb",
        capability=ResearchCapability.search_documents,
        query="observability",
    )
    web_result = await subagents.run_web_research([web_task])
    kb_result = await subagents.run_kb_research([kb_task])

    assert web_result["collected_sources"]
    assert kb_result["collected_sources"]
    # The knowledge-base sub-agent only produces local document sources.
    assert all(
        s.source_id.startswith("doc-") for s in kb_result["collected_sources"]
    )
    assert all(
        not s.source_id.startswith("doc-") for s in web_result["collected_sources"]
    )


async def test_fact_checker_insufficient_without_evidence():
    result = await fact_checker.check_facts("q", [], [])
    assert isinstance(result, FactCheckResult)
    assert result.sufficient_evidence is False


async def test_writer_only_cites_collected_sources():
    sources = [
        Source(source_id="src-1", title="T1", url="u1"),
        Source(source_id="src-2", title="T2", url="u2"),
    ]
    findings = [Finding(claim="c", evidence="e", source_ids=["src-1"])]
    fact_check = FactCheckResult(
        supported_claims=["c"],
        unsupported_claims=[],
        missing_evidence=[],
        sufficient_evidence=True,
    )
    report = await writer.write_report("q", findings, sources, fact_check)

    cited = {s.source_id for s in report.sources}
    assert cited == {"src-1", "src-2"}
    assert 0.0 <= report.confidence <= 1.0
