"""Conditional routing for the research loop.

After fact checking, either loop back to the supervisor (if evidence is
insufficient and the iteration budget allows) — which re-dispatches the
parallel sub-agents — or proceed to the writer. The maximum number of
research iterations is strictly enforced, so the graph can never loop
forever.
"""

from __future__ import annotations

from typing import Literal

from backend.app.config import settings
from backend.app.graph.state import ResearchState
from backend.app.observability.logging import get_logger

logger = get_logger("researchpilot.graph")


def route_after_fact_check(state: ResearchState) -> Literal["supervisor", "writer"]:
    """Decide whether to research again (via supervisor) or write the report."""

    fact_check = state.get("fact_check_results")
    iteration = state.get("iteration_count", 1)
    max_iter = settings.max_research_iterations

    sufficient = fact_check.sufficient_evidence if fact_check else True

    if not sufficient and iteration < max_iter:
        logger.info(
            "route_decision",
            decision="supervisor",
            iteration=iteration,
            max_iterations=max_iter,
            reason="insufficient_evidence",
        )
        return "supervisor"

    logger.info(
        "route_decision",
        decision="writer",
        iteration=iteration,
        max_iterations=max_iter,
        reason="sufficient_or_max_iterations",
    )
    return "writer"
