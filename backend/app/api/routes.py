"""API routes for ResearchPilot."""

from __future__ import annotations

import threading
from collections import OrderedDict

from fastapi import APIRouter, HTTPException

from backend.app.api.schemas import (
    DemoScenarioRequest,
    DemoScenarioResponse,
    FeedbackRequest,
    HealthResponse,
    ReadyResponse,
    ResearchRequest,
    ResearchResponse,
)
from backend.app.config import settings
from backend.app.observability.context import get_context
from backend.app.observability.logging import get_logger
from backend.app.observability.metrics import metrics
from backend.app.services.research import ResearchOutcome, run_research

logger = get_logger("researchpilot.api")

router = APIRouter()

# --- bounded in-memory result store (workshop-local, not a database) -------
_RESULTS_MAX = 200
_results_lock = threading.Lock()
_results: "OrderedDict[str, ResearchOutcome]" = OrderedDict()


def _store_result(outcome: ResearchOutcome) -> None:
    with _results_lock:
        _results[outcome.request_id] = outcome
        while len(_results) > _RESULTS_MAX:
            _results.popitem(last=False)


def _get_result(request_id: str) -> ResearchOutcome | None:
    with _results_lock:
        return _results.get(request_id)


# --- health / readiness ----------------------------------------------------
@router.get("/health", response_model=HealthResponse, tags=["system"])
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service=settings.service_name,
        environment=settings.environment,
    )


@router.get("/ready", response_model=ReadyResponse, tags=["system"])
async def ready() -> ReadyResponse:
    return ReadyResponse(
        status="ready",
        llm_provider=settings.llm_provider.value,
        llm_configured=settings.llm_configured,
        openai_configured=settings.openai_configured,
        langfuse_configured=settings.langfuse_configured,
        demo_scenario=settings.demo_scenario.value,
    )


# --- metrics ---------------------------------------------------------------
@router.get("/api/v1/metrics", tags=["observability"])
async def get_metrics() -> dict:
    return metrics.snapshot()


# --- demo scenario control ---------------------------------------------------
# Lets the frontend switch DEMO_SCENARIO live, without editing .env and
# restarting the backend. Mutates the process-global `settings` singleton —
# the same pattern the test suite already uses to switch scenarios between
# runs. Fine for a single-presenter workshop tool; not meant for concurrent
# multi-user control.
@router.get(
    "/api/v1/demo-scenario", response_model=DemoScenarioResponse, tags=["system"]
)
async def get_demo_scenario() -> DemoScenarioResponse:
    return DemoScenarioResponse(
        demo_scenario=settings.demo_scenario.value, demo_mode=settings.demo_mode
    )


@router.post(
    "/api/v1/demo-scenario", response_model=DemoScenarioResponse, tags=["system"]
)
async def set_demo_scenario(body: DemoScenarioRequest) -> DemoScenarioResponse:
    settings.demo_scenario = body.scenario
    logger.info("demo_scenario_changed", demo_scenario=body.scenario.value)
    return DemoScenarioResponse(
        demo_scenario=settings.demo_scenario.value, demo_mode=settings.demo_mode
    )


# --- research --------------------------------------------------------------
@router.post("/api/v1/research", response_model=ResearchResponse, tags=["research"])
async def research(body: ResearchRequest) -> ResearchResponse:
    ctx = get_context()
    outcome = await run_research(
        question=body.question,
        request_id=ctx.request_id,
        trace_id=ctx.trace_id,
        session_id=ctx.session_id,
        user_id=ctx.user_id,
        thumbs_up=body.thumbs_up,
    )
    _store_result(outcome)
    return ResearchResponse(**outcome.model_dump())


@router.get(
    "/api/v1/research/{request_id}",
    response_model=ResearchResponse,
    tags=["research"],
)
async def get_research(request_id: str) -> ResearchResponse:
    outcome = _get_result(request_id)
    if outcome is None:
        raise HTTPException(status_code=404, detail="request_id not found")
    return ResearchResponse(**outcome.model_dump())


# --- feedback --------------------------------------------------------------
@router.post("/api/v1/feedback", tags=["research"])
async def feedback(body: FeedbackRequest) -> dict:
    outcome = _get_result(body.request_id)
    if outcome is None:
        raise HTTPException(status_code=404, detail="request_id not found")

    updated = outcome.model_copy(update={"thumbs_up": body.thumbs_up})
    _store_result(updated)
    logger.info(
        "user_feedback_recorded",
        target_request_id=body.request_id,
        thumbs_up=body.thumbs_up,
    )
    return {"status": "recorded", "request_id": body.request_id, "thumbs_up": body.thumbs_up}
