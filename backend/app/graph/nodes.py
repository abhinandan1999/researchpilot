"""LangGraph node functions.

Topology:

    planner -> supervisor -> {web_research, kb_research} -> aggregator
             -> fact_check -> (supervisor | writer)

The **supervisor** splits the plan into disjoint task lists and dispatches
two specialist sub-agents that run **in parallel**. Each sub-agent wraps its
work in ``subagent_started / subagent_completed / subagent_failed`` logs,
its own metrics, and (when enabled) its own Langfuse span — so tracing,
logging, and metrics are correctly attributed across the parallel branches.
Because the two sub-agents only ever write to additive-reducer state fields,
their concurrent updates merge safely.
"""

from contextlib import asynccontextmanager
from typing import Any

from langchain_core.runnables import RunnableConfig

from backend.app.agents import fact_checker, llm, planner, subagents, writer
from backend.app.config import DemoScenario, settings
from backend.app.graph.state import ResearchState
from backend.app.models.schemas import FactCheckResult, ResearchPlan, SubAgentReport
from backend.app.observability import langfuse
from backend.app.observability.logging import get_logger
from backend.app.observability.metrics import metrics
from backend.app.utils.time import elapsed_ms, monotonic_ms, utc_now_iso

logger = get_logger("researchpilot.graph")


@asynccontextmanager
async def _agent_span(name: str):
    metrics.incr("agent_runs")
    start = monotonic_ms()
    logger.info("agent_started", agent=name)
    try:
        yield
    except Exception as exc:  # noqa: BLE001
        metrics.incr("agent_failures")
        logger.error(
            "agent_failed",
            agent=name,
            duration_ms=elapsed_ms(start),
            status="failed",
            error_type=type(exc).__name__,
            error=str(exc),
        )
        raise
    else:
        logger.info(
            "agent_completed", agent=name, duration_ms=elapsed_ms(start), status="ok"
        )


def _active_scenario() -> DemoScenario:
    return settings.demo_scenario if settings.demo_mode else DemoScenario.normal


async def planner_node(state: ResearchState, config: RunnableConfig | None = None) -> dict:
    async with _agent_span("planner"):
        plan = await planner.plan_research(state["question"], config=config)

        # Demo scenario: expensive_agent performs a redundant extra LLM call.
        if _active_scenario() is DemoScenario.expensive_agent:
            await llm.structured_completion(
                ResearchPlan,
                system="Restate the plan objective. This is a redundant call.",
                user=f"Question: {state['question']}",
                agent_name="planner_redundant",
                config=config,
            )
    return {"research_plan": plan}


async def supervisor_node(
    state: ResearchState, config: RunnableConfig | None = None
) -> dict:
    """Split the plan and dispatch the parallel research sub-agents.

    Runs alone (never concurrently), so it is the single writer of the
    scalar ``iteration_count`` and ``subagent_tasks`` fields that the
    parallel sub-agents read.
    """

    iteration = state.get("iteration_count", 0) + 1
    async with _agent_span("supervisor"):
        plan = state["research_plan"]
        task_split = subagents.split_tasks(plan)
        dispatched = [name for name, tasks in task_split.items() if tasks]

        metrics.incr("supervisor_dispatches")
        if len(dispatched) > 1:
            metrics.incr("parallel_dispatches")

        logger.info(
            "supervisor_dispatch",
            iteration=iteration,
            mode="parallel" if len(dispatched) > 1 else "single",
            subagents=dispatched,
            tasks_per_agent={name: len(tasks) for name, tasks in task_split.items()},
        )
    logger.info("research_iteration_started", iteration=iteration)
    return {"subagent_tasks": task_split, "iteration_count": iteration}


@asynccontextmanager
async def _subagent_span(agent: str, group: str, task_count: int):
    """Observe one parallel sub-agent: logs, metrics, and a Langfuse span.

    Yields a mutable box the caller fills with result counts; on success a
    :class:`SubAgentReport` is emitted so the aggregator can attribute
    sources/findings/errors and wall time to this specific sub-agent.
    """

    metrics.incr("subagent_runs")
    metrics.incr("parallel_subagent_runs")
    start = monotonic_ms()
    started_at = utc_now_iso()
    logger.info(
        "subagent_started", agent=agent, parallel_group=group, tasks=task_count
    )
    box: dict[str, Any] = {"report": None}
    with langfuse.tool_span(f"subagent:{agent}", agent=agent, parallel_group=group):
        try:
            yield box
        except Exception as exc:  # noqa: BLE001
            metrics.incr("subagent_failures")
            logger.error(
                "subagent_failed",
                agent=agent,
                parallel_group=group,
                duration_ms=elapsed_ms(start),
                status="failed",
                error_type=type(exc).__name__,
                error=str(exc),
            )
            raise
    counts = box.get("counts", {})
    duration = elapsed_ms(start)
    logger.info(
        "subagent_completed",
        agent=agent,
        parallel_group=group,
        duration_ms=duration,
        status="ok",
        sources=counts.get("sources", 0),
        findings=counts.get("findings", 0),
        errors=counts.get("errors", 0),
    )
    box["report"] = SubAgentReport(
        agent=agent,
        parallel_group=group,
        task_count=task_count,
        source_count=counts.get("sources", 0),
        finding_count=counts.get("findings", 0),
        error_count=counts.get("errors", 0),
        duration_ms=duration,
        started_at=started_at,
        completed_at=utc_now_iso(),
    )


async def _run_subagent(state: ResearchState, agent: str, runner) -> dict:
    """Shared body for the parallel research sub-agent nodes."""

    group = "research"
    tasks = state.get("subagent_tasks", {}).get(agent, [])
    existing = {s.source_id for s in state.get("collected_sources", [])}
    async with _subagent_span(agent, group, len(tasks)) as box:
        result = await runner(tasks, existing_source_ids=existing)
        box["counts"] = {
            "sources": len(result["collected_sources"]),
            "findings": len(result["findings"]),
            "errors": len(result["errors"]),
        }
    # Only additive-reducer fields are returned, so parallel branches merge.
    return {
        "collected_sources": result["collected_sources"],
        "findings": result["findings"],
        "errors": result["errors"],
        "subagent_reports": [box["report"]],
    }


async def web_research_node(
    state: ResearchState, config: RunnableConfig | None = None
) -> dict:
    return await _run_subagent(state, subagents.WEB_AGENT, subagents.run_web_research)


async def kb_research_node(
    state: ResearchState, config: RunnableConfig | None = None
) -> dict:
    return await _run_subagent(state, subagents.KB_AGENT, subagents.run_kb_research)


async def aggregator_node(
    state: ResearchState, config: RunnableConfig | None = None
) -> dict:
    """Join point after the parallel sub-agents (fan-in).

    Runs once, after *both* sub-agents complete. Evidence has already been
    merged by the additive reducers; this node only records the join for
    observability and must not re-emit additive fields (that would double
    them).
    """

    iteration = state.get("iteration_count", 1)
    reports = state.get("subagent_reports", [])
    async with _agent_span("aggregator"):
        logger.info(
            "subagents_joined",
            iteration=iteration,
            subagents=[r.agent for r in reports],
            total_sources=len(state.get("collected_sources", [])),
            total_findings=len(state.get("findings", [])),
            per_agent={r.agent: r.source_count for r in reports},
        )
    logger.info(
        "research_iteration_completed",
        iteration=iteration,
        sources=len(state.get("collected_sources", [])),
        findings=len(state.get("findings", [])),
    )
    return {}


async def fact_check_node(state: ResearchState, config: RunnableConfig | None = None) -> dict:
    async with _agent_span("fact_checker"):
        result = await fact_checker.check_facts(
            state["question"],
            state.get("findings", []),
            state.get("collected_sources", []),
            config=config,
        )

    iteration = state.get("iteration_count", 1)
    # Demo scenario: agent_loop forces one extra research iteration.
    if (
        _active_scenario() is DemoScenario.agent_loop
        and iteration < settings.max_research_iterations
        and result.sufficient_evidence
    ):
        result = FactCheckResult(
            supported_claims=result.supported_claims,
            unsupported_claims=result.unsupported_claims,
            missing_evidence=result.missing_evidence
            + ["Demo scenario 'agent_loop': forcing an additional research pass"],
            sufficient_evidence=False,
        )

    return {
        "fact_check_results": result,
        "evidence_gaps": result.missing_evidence,
    }


async def writer_node(state: ResearchState, config: RunnableConfig | None = None) -> dict:
    async with _agent_span("writer"):
        report = await writer.write_report(
            state["question"],
            state.get("findings", []),
            state.get("collected_sources", []),
            state["fact_check_results"],
            config=config,
        )
    return {"final_report": report}
