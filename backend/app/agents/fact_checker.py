"""Fact Checker agent.

Reviews collected evidence, separates supported from unsupported claims,
identifies evidence gaps, and decides whether more research is needed.
"""

from __future__ import annotations

from typing import Any

from backend.app.agents import llm
from backend.app.models.schemas import FactCheckResult, Finding, Source

SYSTEM_PROMPT = """You are the Fact Checker agent.
You are given research findings (each with a claim, supporting evidence,
and cited source ids) and the list of available source ids.

Decide, for each claim, whether the evidence genuinely supports it.
- supported_claims: claims backed by relevant evidence from an available source
- unsupported_claims: claims lacking adequate evidence or citing unknown sources
- missing_evidence: important aspects of the question not yet covered
- sufficient_evidence: true only if the collected evidence is enough to write
  a grounded, useful answer

Be strict but fair. Never fabricate evidence."""


def _render_findings(findings: list[Finding], sources: list[Source]) -> str:
    source_ids = ", ".join(sorted({s.source_id for s in sources})) or "(none)"
    lines = [f"Available source ids: {source_ids}", "", "Findings:"]
    for i, f in enumerate(findings, 1):
        cites = ", ".join(f.source_ids) or "(none)"
        lines.append(f"{i}. claim={f.claim!r} evidence={f.evidence[:200]!r} cites=[{cites}]")
    if not findings:
        lines.append("(no findings were collected)")
    return "\n".join(lines)


async def check_facts(
    question: str,
    findings: list[Finding],
    sources: list[Source],
    *,
    config: dict[str, Any] | None = None,
) -> FactCheckResult:
    """Assess whether collected evidence is sufficient and grounded."""

    # No evidence at all -> deterministically insufficient (no LLM needed).
    if not findings or not sources:
        return FactCheckResult(
            supported_claims=[],
            unsupported_claims=[],
            missing_evidence=["No supporting evidence was collected"],
            sufficient_evidence=False,
        )

    user = (
        f"Research question:\n{question}\n\n"
        f"{_render_findings(findings, sources)}"
    )
    return await llm.structured_completion(
        FactCheckResult,
        system=SYSTEM_PROMPT,
        user=user,
        agent_name="fact_checker",
        config=config,
    )
