"""Typed LangGraph state for the research workflow."""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from backend.app.models.schemas import (
    FactCheckResult,
    Finding,
    ResearchPlan,
    ResearchReport,
    ResearchTask,
    Source,
    SubAgentReport,
)


class ResearchState(TypedDict, total=False):
    """Shared state passed between graph nodes.

    List fields use additive reducers so evidence accumulates across
    research iterations. Scalar fields are overwritten by the node that
    produces them.

    The supervisor writes ``subagent_tasks`` (a per-sub-agent task split);
    the two research sub-agents then run in parallel and only ever write to
    additive-reducer fields, so their concurrent updates merge safely.
    """

    # Correlation identifiers
    request_id: str
    trace_id: str
    session_id: str

    # Input
    question: str

    # Planner output
    research_plan: ResearchPlan | None

    # Supervisor output: per-sub-agent task split (agent name -> tasks)
    subagent_tasks: dict[str, list[ResearchTask]]

    # Research output (accumulated across iterations and parallel sub-agents)
    collected_sources: Annotated[list[Source], operator.add]
    findings: Annotated[list[Finding], operator.add]

    # Per-sub-agent execution records (accumulated across parallel branches)
    subagent_reports: Annotated[list[SubAgentReport], operator.add]

    # Fact checking
    fact_check_results: FactCheckResult | None
    evidence_gaps: list[str]

    # Loop control
    iteration_count: int

    # Final output
    final_report: ResearchReport | None

    # Errors (accumulated)
    errors: Annotated[list[dict[str, Any]], operator.add]

    # Per-run metrics / metadata
    metrics: dict[str, Any]
