"""Research agent.

Executes the tasks in a :class:`ResearchPlan` using the allowed local
tools only (dispatch is by capability enum — never arbitrary execution).
Tool failures for individual tasks are captured and the investigation
continues so the workflow can degrade gracefully.
"""

from __future__ import annotations

from backend.app.models.schemas import (
    Finding,
    ResearchCapability,
    ResearchPlan,
    ResearchTask,
    Source,
)
from backend.app.observability.logging import get_logger
from backend.app.tools.documents import search_documents
from backend.app.tools.search import search_sources
from backend.app.tools.sources import get_source
from backend.app.utils.errors import ResearchPilotError

logger = get_logger("researchpilot.researcher")


def _passage_to_source(document: str, title: str, passage: str, relevance: float) -> Source:
    stem = document.rsplit(".", 1)[0]
    return Source(
        source_id=f"doc-{stem}",
        title=title,
        url=f"file://data/documents/{document}",
        topic="local-document",
        snippet=passage,
        relevance=relevance,
        is_demo=True,
    )


async def execute_tasks(
    tasks: list[ResearchTask],
    *,
    existing_source_ids: set[str] | None = None,
) -> dict:
    """Execute a list of research tasks, returning sources, findings, errors.

    Dispatch is by capability enum only (never arbitrary execution). Tool
    failures for individual tasks are captured and execution continues so
    the workflow degrades gracefully. This is the shared execution core used
    by the research sub-agents.
    """

    seen: set[str] = set(existing_source_ids or set())
    collected: list[Source] = []
    findings: list[Finding] = []
    errors: list[dict] = []

    for task in tasks:
        try:
            if task.capability is ResearchCapability.search_sources:
                result = await search_sources(task.query)
                for src in result.sources:
                    if src.source_id not in seen:
                        seen.add(src.source_id)
                        collected.append(src)
                    findings.append(
                        Finding(
                            claim=src.title,
                            evidence=src.snippet,
                            source_ids=[src.source_id],
                        )
                    )

            elif task.capability is ResearchCapability.search_documents:
                doc_result = await search_documents(task.query)
                for passage in doc_result.passages:
                    src = _passage_to_source(
                        passage.document,
                        passage.title,
                        passage.passage,
                        passage.relevance,
                    )
                    if src.source_id not in seen:
                        seen.add(src.source_id)
                        collected.append(src)
                    findings.append(
                        Finding(
                            claim=passage.title,
                            evidence=passage.passage,
                            source_ids=[src.source_id],
                        )
                    )

            elif task.capability is ResearchCapability.get_source:
                src = await get_source(task.query)
                if src.source_id not in seen:
                    seen.add(src.source_id)
                    collected.append(src)
                findings.append(
                    Finding(
                        claim=src.title,
                        evidence=src.snippet,
                        source_ids=[src.source_id],
                    )
                )

        except ResearchPilotError as exc:
            logger.warning(
                "research_task_failed",
                capability=task.capability.value,
                error_type=exc.error_type,
                error=exc.message,
            )
            errors.append(
                {
                    "stage": "research",
                    "capability": task.capability.value,
                    "error_type": exc.error_type,
                    "message": exc.message,
                }
            )

    return {
        "collected_sources": collected,
        "findings": findings,
        "errors": errors,
    }


async def execute_plan(
    plan: ResearchPlan,
    *,
    existing_source_ids: set[str] | None = None,
) -> dict:
    """Execute all plan tasks (backward-compatible single-agent entry point)."""

    return await execute_tasks(
        plan.tasks, existing_source_ids=existing_source_ids
    )
