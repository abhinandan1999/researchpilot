"""Research orchestration service.

Runs one research request end-to-end: validates input, invokes the
LangGraph workflow (with Langfuse tracing), evaluates the result, and
assembles a fully-typed outcome plus a per-request observability summary.
"""

from __future__ import annotations

from pydantic import BaseModel

from backend.app.config import settings
from backend.app.evaluation.evaluator import heuristic_evaluation
from backend.app.graph.graph import get_graph
from backend.app.models.schemas import (
    EvaluationResult,
    ObservabilitySummary,
    ResearchReport,
)
from backend.app.observability import langfuse
from backend.app.observability.logging import get_logger
from backend.app.observability.metrics import (
    get_request_metrics,
    metrics,
    start_request_metrics,
)
from backend.app.observability.redaction import (
    pseudonymize_user,
    safe_question_metadata,
)
from backend.app.utils.errors import ResearchPilotError, ValidationError
from backend.app.utils.time import elapsed_ms, monotonic_ms

logger = get_logger("researchpilot.service")


class ResearchOutcome(BaseModel):
    """Full result of a research request."""

    request_id: str
    trace_id: str
    session_id: str
    status: str
    report: ResearchReport
    evaluation: EvaluationResult
    observability: ObservabilitySummary
    errors: list[dict] = []
    thumbs_up: bool | None = None


def _validate_question(question: str) -> str:
    q = (question or "").strip()
    if not q:
        raise ValidationError("question must not be empty")
    if len(q) > settings.max_question_length:
        raise ValidationError(
            f"question exceeds maximum length of {settings.max_question_length}"
        )
    return q


async def run_research(
    *,
    question: str,
    request_id: str,
    trace_id: str,
    session_id: str,
    user_id: str | None = None,
    thumbs_up: bool | None = None,
) -> ResearchOutcome:
    """Execute the research workflow and return a typed outcome."""

    question = _validate_question(question)
    start_request_metrics()
    metrics.incr("requests_total")
    start = monotonic_ms()

    safe_meta = safe_question_metadata(
        question, capture_input=settings.langfuse_capture_input
    )
    trace_metadata = {
        "request_id": request_id,
        "environment": settings.environment,
        "model": settings.openai_model,
        "demo_scenario": settings.demo_scenario.value,
        **safe_meta,
    }

    # Scenario-qualified trace name (e.g. "parallel_research_request") so
    # traces are identifiable at a glance in Langfuse's flat list view,
    # instead of every run showing up under the same generic name.
    trace_name = f"{settings.demo_scenario.value}_request"

    config = langfuse.build_run_config(
        run_name=trace_name,
        session_id=session_id,
        user_id=pseudonymize_user(user_id),
        metadata=trace_metadata,
        tags=[settings.environment, f"scenario:{settings.demo_scenario.value}"],
    )

    initial_state = {
        "request_id": request_id,
        "trace_id": trace_id,
        "session_id": session_id,
        "question": question,
        "collected_sources": [],
        "findings": [],
        "subagent_reports": [],
        "errors": [],
        "iteration_count": 0,
    }

    logger.info("request_started", **safe_meta)

    graph = get_graph()
    try:
        with langfuse.research_trace(
            trace_name, metadata=trace_metadata
        ) as trace:
            final_state = await graph.ainvoke(initial_state, config=config)
    except ResearchPilotError:
        metrics.incr("requests_failed")
        metrics.observe_latency(elapsed_ms(start))
        logger.error("request_failed", status="failed")
        raise
    except Exception as exc:  # noqa: BLE001
        metrics.incr("requests_failed")
        metrics.observe_latency(elapsed_ms(start))
        logger.error("request_failed", status="failed", error=str(exc))
        raise ResearchPilotError(f"Research workflow failed: {exc}") from exc

    report = final_state.get("final_report")
    if report is None:
        metrics.incr("requests_failed")
        metrics.observe_latency(elapsed_ms(start))
        raise ResearchPilotError("Workflow completed without producing a report")

    findings = final_state.get("findings", [])
    sources = final_state.get("collected_sources", [])
    fact_check = final_state.get("fact_check_results")
    errors = final_state.get("errors", [])

    evaluation = heuristic_evaluation(report, findings, sources, fact_check)
    logger.info(
        "evaluation_completed",
        overall=evaluation.overall,
        completeness=evaluation.completeness,
        groundedness=evaluation.groundedness,
        evidence_coverage=evaluation.evidence_coverage,
    )

    # Attach evaluation (and optional user feedback) to the SAME trace as the
    # request (reuse `trace` from above — opening a new research_trace() here
    # would score a separate, unrelated trace instead).
    try:
        trace.score("heuristic_overall", evaluation.overall)
        if thumbs_up is not None:
            trace.score("user_feedback", 1.0 if thumbs_up else 0.0)
    except Exception:  # pragma: no cover - defensive
        pass

    duration_ms = elapsed_ms(start)
    metrics.incr("requests_success")
    metrics.observe_latency(duration_ms)

    rm = get_request_metrics()
    subagent_reports = final_state.get("subagent_reports", [])
    observability = ObservabilitySummary(
        duration_ms=duration_ms,
        agent_count=rm.get("agent_runs", 0),
        tool_call_count=rm.get("tool_calls", 0),
        llm_call_count=rm.get("llm_calls", 0),
        input_tokens=rm.get("input_tokens", 0),
        output_tokens=rm.get("output_tokens", 0),
        iterations=final_state.get("iteration_count", 0),
        retries=rm.get("retries", 0),
        tool_timeouts=rm.get("tool_timeouts", 0),
        evaluation_score=evaluation.overall,
        demo_scenario=settings.demo_scenario.value,
        subagent_count=rm.get("subagent_runs", 0),
        parallel_dispatches=rm.get("parallel_dispatches", 0),
        subagent_reports=subagent_reports,
    )

    logger.info(
        "request_completed",
        status="completed",
        duration_ms=duration_ms,
        agent_count=observability.agent_count,
        subagent_count=observability.subagent_count,
        parallel_dispatches=observability.parallel_dispatches,
        tool_call_count=observability.tool_call_count,
        llm_call_count=observability.llm_call_count,
        iterations=observability.iterations,
    )

    langfuse.flush()

    return ResearchOutcome(
        request_id=request_id,
        trace_id=trace_id,
        session_id=session_id,
        status="completed",
        report=report,
        evaluation=evaluation,
        observability=observability,
        errors=errors,
        thumbs_up=thumbs_up,
    )
