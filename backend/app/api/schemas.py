"""API request/response schemas.

These wrap the domain models for the HTTP boundary. Domain models are
reused directly where their shape already matches the API contract.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from backend.app.config import DemoScenario, settings
from backend.app.models.schemas import (
    EvaluationResult,
    ObservabilitySummary,
    ResearchReport,
)


class ResearchRequest(BaseModel):
    """Body of ``POST /api/v1/research``."""

    question: str = Field(..., min_length=1, max_length=settings.max_question_length)
    thumbs_up: bool | None = Field(
        default=None,
        description="Optional user feedback: true (up), false (down), or null.",
    )


class ResearchResponse(BaseModel):
    """Response of ``POST /api/v1/research``."""

    request_id: str
    trace_id: str
    session_id: str
    status: str
    report: ResearchReport
    evaluation: EvaluationResult
    observability: ObservabilitySummary
    errors: list[dict] = Field(default_factory=list)


class FeedbackRequest(BaseModel):
    """Body of the feedback endpoint."""

    request_id: str
    thumbs_up: bool | None = None


class HealthResponse(BaseModel):
    status: str
    service: str
    environment: str


class ReadyResponse(BaseModel):
    status: str
    openai_configured: bool
    langfuse_configured: bool
    demo_scenario: str


class ErrorResponse(BaseModel):
    error: str
    error_type: str
    request_id: str | None = None


class DemoScenarioRequest(BaseModel):
    """Body of ``POST /api/v1/demo-scenario``."""

    scenario: DemoScenario


class DemoScenarioResponse(BaseModel):
    demo_scenario: str
    demo_mode: bool
    options: list[str] = Field(default_factory=lambda: [s.value for s in DemoScenario])
