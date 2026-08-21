"""LangGraph assembly for the ResearchPilot workflow.

    START -> planner -> supervisor -> {web_research, kb_research}
          -> aggregator -> fact_check -> (supervisor | writer) -> END

The supervisor fans out to two research sub-agents that execute in
parallel; the aggregator is the fan-in join. The compiled graph is cached
so it is built once per process.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from langgraph.graph import END, START, StateGraph

from backend.app.graph.nodes import (
    aggregator_node,
    fact_check_node,
    kb_research_node,
    planner_node,
    supervisor_node,
    web_research_node,
    writer_node,
)
from backend.app.graph.routing import route_after_fact_check
from backend.app.graph.state import ResearchState


def build_graph() -> Any:
    """Construct and compile the research StateGraph."""

    builder = StateGraph(ResearchState)

    builder.add_node("planner", planner_node)
    builder.add_node("supervisor", supervisor_node)
    builder.add_node("web_research", web_research_node)
    builder.add_node("kb_research", kb_research_node)
    builder.add_node("aggregator", aggregator_node)
    builder.add_node("fact_check", fact_check_node)
    builder.add_node("writer", writer_node)

    builder.add_edge(START, "planner")
    builder.add_edge("planner", "supervisor")

    # Fan-out: the supervisor dispatches both sub-agents in parallel.
    builder.add_edge("supervisor", "web_research")
    builder.add_edge("supervisor", "kb_research")

    # Fan-in: the aggregator runs once both sub-agents complete.
    builder.add_edge("web_research", "aggregator")
    builder.add_edge("kb_research", "aggregator")

    builder.add_edge("aggregator", "fact_check")
    builder.add_conditional_edges(
        "fact_check",
        route_after_fact_check,
        {"supervisor": "supervisor", "writer": "writer"},
    )
    builder.add_edge("writer", END)

    return builder.compile()


@lru_cache(maxsize=1)
def get_graph() -> Any:
    """Return the compiled graph (built once)."""

    return build_graph()
