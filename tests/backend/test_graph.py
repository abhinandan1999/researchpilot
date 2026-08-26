"""Tests for the LangGraph workflow and routing."""

from __future__ import annotations

from backend.app.config import DemoScenario, settings
from backend.app.graph.graph import get_graph
from backend.app.graph.routing import route_after_fact_check
from backend.app.models.schemas import FactCheckResult, ResearchReport


def _initial_state(question: str = "How to build reliable AI agents?") -> dict:
    return {
        "request_id": "req_test",
        "trace_id": "trace_test",
        "session_id": "sess_test",
        "question": question,
        "collected_sources": [],
        "findings": [],
        "subagent_reports": [],
        "errors": [],
        "iteration_count": 0,
    }


async def test_graph_normal_run_produces_report():
    graph = get_graph()
    final = await graph.ainvoke(_initial_state())
    assert isinstance(final["final_report"], ResearchReport)
    assert final["iteration_count"] == 1
    assert final["final_report"].summary


async def test_graph_dispatches_two_parallel_subagents():
    graph = get_graph()
    final = await graph.ainvoke(_initial_state())
    reports = final["subagent_reports"]
    agents = {r.agent for r in reports}
    # The supervisor fans out to both specialist sub-agents.
    assert agents == {"web_research", "kb_research"}
    # Each sub-agent contributed evidence from its own capability slice.
    assert any(r.source_count > 0 for r in reports)


async def test_graph_parallel_research_scenario_runs_both_subagents():
    settings.demo_scenario = DemoScenario.parallel_research
    graph = get_graph()
    final = await graph.ainvoke(_initial_state())
    assert isinstance(final["final_report"], ResearchReport)
    reports = {r.agent: r for r in final["subagent_reports"]}
    assert set(reports) == {"web_research", "kb_research"}
    # Under this scenario web is deliberately slower than kb.
    assert reports["web_research"].duration_ms > reports["kb_research"].duration_ms


async def test_graph_agent_loop_runs_two_iterations():
    settings.demo_scenario = DemoScenario.agent_loop
    graph = get_graph()
    final = await graph.ainvoke(_initial_state())
    # agent_loop forces exactly one extra research iteration (max = 2).
    assert final["iteration_count"] == settings.max_research_iterations
    assert isinstance(final["final_report"], ResearchReport)


def test_route_back_to_supervisor_when_insufficient():
    state = {
        "fact_check_results": FactCheckResult(
            supported_claims=[],
            unsupported_claims=[],
            missing_evidence=[],
            sufficient_evidence=False,
        ),
        "iteration_count": 1,
    }
    assert route_after_fact_check(state) == "supervisor"


def test_route_to_writer_at_max_iterations():
    state = {
        "fact_check_results": FactCheckResult(
            supported_claims=[],
            unsupported_claims=[],
            missing_evidence=[],
            sufficient_evidence=False,
        ),
        "iteration_count": settings.max_research_iterations,
    }
    assert route_after_fact_check(state) == "writer"


def test_route_to_writer_when_sufficient():
    state = {
        "fact_check_results": FactCheckResult(
            supported_claims=[],
            unsupported_claims=[],
            missing_evidence=[],
            sufficient_evidence=True,
        ),
        "iteration_count": 1,
    }
    assert route_after_fact_check(state) == "writer"
