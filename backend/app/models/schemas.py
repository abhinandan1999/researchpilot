"""Core Pydantic domain models shared across agents, graph, and API.

These are the canonical data structures produced and consumed by the
agent workflow. Structured LLM outputs validate against these models.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


# --------------------------------------------------------------------------
# Research capabilities the planner may select from (allow-list).
# --------------------------------------------------------------------------
class ResearchCapability(str, Enum):
    """Explicitly allowed research capabilities for the planner."""

    search_sources = "search_sources"
    search_documents = "search_documents"
    get_source = "get_source"


# --------------------------------------------------------------------------
# Sources & tool results
# --------------------------------------------------------------------------
class Source(BaseModel):
    """A demo/local research source."""

    source_id: str
    title: str
    url: str
    topic: str = ""
    snippet: str = ""
    relevance: float = Field(default=0.0, ge=0.0, le=1.0)
    published_at: str | None = None
    is_demo: bool = True


class DocumentPassage(BaseModel):
    """A relevant passage extracted from a local markdown document."""

    document: str
    title: str
    passage: str
    relevance: float = Field(default=0.0, ge=0.0, le=1.0)


class SearchResult(BaseModel):
    """Result of a ``search_sources`` call."""

    query: str
    sources: list[Source] = Field(default_factory=list)


class DocumentSearchResult(BaseModel):
    """Result of a ``search_documents`` call."""

    query: str
    passages: list[DocumentPassage] = Field(default_factory=list)


# --------------------------------------------------------------------------
# Planner
# --------------------------------------------------------------------------
class ResearchTask(BaseModel):
    """A single planned research task."""

    description: str
    capability: ResearchCapability
    query: str


class ResearchPlan(BaseModel):
    """Structured output of the Planner agent."""

    objective: str
    tasks: list[ResearchTask] = Field(default_factory=list)


# --------------------------------------------------------------------------
# Findings & fact checking
# --------------------------------------------------------------------------
class Finding(BaseModel):
    """A single research finding backed by source evidence."""

    claim: str
    evidence: str = ""
    source_ids: list[str] = Field(default_factory=list)


class FactCheckResult(BaseModel):
    """Structured output of the Fact Checker agent."""

    supported_claims: list[str] = Field(default_factory=list)
    unsupported_claims: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    sufficient_evidence: bool = True


# --------------------------------------------------------------------------
# Sub-agent reporting (supervisor / parallel fan-out observability)
# --------------------------------------------------------------------------
class SubAgentReport(BaseModel):
    """A per-sub-agent execution record produced under the supervisor.

    Emitted by each parallel research sub-agent so the aggregator and the
    observability layer can attribute sources, findings, errors, and wall
    time to the individual sub-agent that produced them.
    """

    agent: str
    parallel_group: str = ""
    task_count: int = 0
    source_count: int = 0
    finding_count: int = 0
    error_count: int = 0
    duration_ms: float = 0.0
    started_at: str = ""
    completed_at: str = ""


# --------------------------------------------------------------------------
# Final report
# --------------------------------------------------------------------------
class ReportSource(BaseModel):
    """A source citation in the final report."""

    source_id: str
    title: str
    url: str
    is_demo: bool = True


class ResearchReport(BaseModel):
    """Structured output of the Writer agent / final report."""

    summary: str
    key_findings: list[str] = Field(default_factory=list)
    analysis: str = ""
    sources: list[ReportSource] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


# --------------------------------------------------------------------------
# Evaluation
# --------------------------------------------------------------------------
class EvaluationResult(BaseModel):
    """Result of the lightweight heuristic evaluator.

    This is a *heuristic* evaluation and does not claim authoritative
    correctness. Scores range from 0.0 to 1.0.
    """

    completeness: float = Field(default=0.0, ge=0.0, le=1.0)
    groundedness: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence_coverage: float = Field(default=0.0, ge=0.0, le=1.0)
    overall: float = Field(default=0.0, ge=0.0, le=1.0)
    notes: list[str] = Field(default_factory=list)
    method: str = "heuristic_evaluation"


# --------------------------------------------------------------------------
# Observability summary attached to responses
# --------------------------------------------------------------------------
class ObservabilitySummary(BaseModel):
    """Per-request observability numbers returned to the client."""

    duration_ms: float = 0.0
    agent_count: int = 0
    tool_call_count: int = 0
    llm_call_count: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    iterations: int = 0
    retries: int = 0
    tool_timeouts: int = 0
    evaluation_score: float | None = None
    demo_scenario: str = "normal"
    # Supervisor / parallel fan-out visibility.
    subagent_count: int = 0
    parallel_dispatches: int = 0
    subagent_reports: list[SubAgentReport] = Field(default_factory=list)
