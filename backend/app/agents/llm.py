"""Shared LLM helper used by all agents.

Centralizes OpenAI/LangChain access so agents stay small and testable.
Unit tests monkeypatch :func:`structured_completion` to avoid real
network calls. Token usage is recorded into the metrics collector, and
LLM calls inherit the Langfuse callbacks passed via ``config``.
"""

from __future__ import annotations

import asyncio
from typing import Any, TypeVar

from pydantic import BaseModel

from backend.app.config import LLMProvider, settings
from backend.app.observability.logging import get_logger
from backend.app.observability.metrics import metrics
from backend.app.utils.errors import LLMError

logger = get_logger("researchpilot.llm")

TModel = TypeVar("TModel", bound=BaseModel)


def get_chat_model(temperature: float = 0.2) -> Any:
    """Create a configured chat model instance for the active provider."""

    if settings.llm_provider is LLMProvider.ollama:
        from langchain_ollama import ChatOllama

        return ChatOllama(
            model=settings.ollama_model,
            base_url=settings.ollama_base_url,
            temperature=temperature,
            timeout=settings.llm_timeout_seconds,
        )

    from langchain_openai import ChatOpenAI

    if not settings.openai_configured:
        raise LLMError("OPENAI_API_KEY is not configured")

    return ChatOpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
        temperature=temperature,
        timeout=settings.llm_timeout_seconds,
        max_retries=0,  # retries handled explicitly by the app
    )


def _record_tokens(raw: Any) -> None:
    usage = getattr(raw, "usage_metadata", None) or {}
    input_tokens = int(usage.get("input_tokens", 0) or 0)
    output_tokens = int(usage.get("output_tokens", 0) or 0)
    if input_tokens:
        metrics.incr("input_tokens", input_tokens)
    if output_tokens:
        metrics.incr("output_tokens", output_tokens)


async def structured_completion(
    schema: type[TModel],
    *,
    system: str,
    user: str,
    agent_name: str,
    config: dict[str, Any] | None = None,
    temperature: float = 0.2,
) -> TModel:
    """Invoke the LLM and return a validated ``schema`` instance.

    Bounded by ``LLM_TIMEOUT_SECONDS``. Raises :class:`LLMError` on
    failure or timeout.
    """

    metrics.incr("llm_calls")
    model = get_chat_model(temperature=temperature)
    structured = model.with_structured_output(schema, include_raw=True)
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]

    # Override run_name with the actual agent (planner/fact_checker/writer/
    # planner_redundant) for this specific call, so it's identifiable in
    # Langfuse instead of showing up as a generic ChatOpenAI/RunnableSequence
    # node. Everything else in config (callbacks, metadata) is preserved so
    # tracing still nests under the right request.
    run_config = {**(config or {}), "run_name": agent_name}

    try:
        result = await asyncio.wait_for(
            structured.ainvoke(messages, config=run_config),
            timeout=settings.llm_timeout_seconds,
        )
    except asyncio.TimeoutError as exc:
        logger.error("llm_timeout", agent=agent_name, error_type="LLMError")
        raise LLMError(f"LLM call for '{agent_name}' timed out") from exc
    except Exception as exc:  # noqa: BLE001 - normalize to LLMError
        logger.error("llm_failed", agent=agent_name, error=str(exc))
        raise LLMError(f"LLM call for '{agent_name}' failed: {exc}") from exc

    # include_raw=True -> {"raw": AIMessage, "parsed": schema, "parsing_error": ...}
    parsed = result.get("parsed") if isinstance(result, dict) else result
    if isinstance(result, dict):
        _record_tokens(result.get("raw"))
        if parsed is None:
            raise LLMError(
                f"LLM structured output for '{agent_name}' failed validation"
            )
    return parsed  # type: ignore[return-value]
