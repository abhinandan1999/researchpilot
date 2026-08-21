"""FastAPI application entrypoint for ResearchPilot."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.app.api.middleware import RequestContextMiddleware
from backend.app.api.routes import router
from backend.app.config import settings
from backend.app.observability import langfuse
from backend.app.observability.context import get_context
from backend.app.observability.logging import configure_logging, get_logger
from backend.app.utils.errors import ResearchPilotError

logger = get_logger("researchpilot.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    langfuse.init_langfuse()
    logger.info(
        "startup",
        environment=settings.environment,
        demo_mode=settings.demo_mode,
        demo_scenario=settings.demo_scenario.value,
        openai_configured=settings.openai_configured,
        langfuse_configured=settings.langfuse_configured,
    )
    try:
        yield
    finally:
        langfuse.flush()
        logger.info("shutdown")


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(
        title="ResearchPilot",
        description="Observable Multi-Agent Research Assistant (workshop)",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS so the local Streamlit frontend can call the API.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "X-Trace-ID", "X-Session-ID"],
    )
    app.add_middleware(RequestContextMiddleware)

    app.include_router(router)

    @app.exception_handler(ResearchPilotError)
    async def _domain_error_handler(request: Request, exc: ResearchPilotError):
        ctx = get_context()
        logger.error(
            "domain_error",
            error_type=exc.error_type,
            error=exc.message,
            status_code=exc.http_status,
        )
        return JSONResponse(
            status_code=exc.http_status,
            content={
                "error": exc.message,
                "error_type": exc.error_type,
                "request_id": ctx.request_id,
            },
        )

    @app.exception_handler(Exception)
    async def _unexpected_error_handler(request: Request, exc: Exception):
        ctx = get_context()
        # Log the stack trace internally; never expose it to the client.
        logger.error(
            "unexpected_error",
            error_type=type(exc).__name__,
            error=str(exc),
            exc_info=True,
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal server error",
                "error_type": "InternalServerError",
                "request_id": ctx.request_id,
            },
        )

    return app


app = create_app()
