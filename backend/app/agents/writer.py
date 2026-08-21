"""Writer agent.

Generates the final :class:`ResearchReport` from verified evidence only.
The writer must not invent sources: the report's ``sources`` are rebuilt
from the actually-collected sources, never from free-form model output.
"""

from __future__ import annotations

from typing import Any

from backend.app.agents import llm
from backend.app.models.schemas import (
    FactCheckResult,
    Finding,
    ReportSource,
    ResearchReport,
    Source,
)

SYSTEM_PROMPT = """You are the Writer agent.
Write a concise, well-structured research report that answers the question
using ONLY the verified findings and evidence provided. Do not invent facts
or sources. If evidence is thin, say so and lower your confidence.

Produce:
- summary: 2-4 sentence answer
- key_findings: 3-6 short bullet points, each grounded in the evidence
- analysis: a few paragraphs synthesizing the findings
- confidence: 0.0-1.0 reflecting how well the evidence supports the answer
Leave the sources list empty; it will be populated from the cited evidence."""


def _render(findings: list[Finding], fact_check: FactCheckResult) -> str:
    lines = ["Verified findings:"]
    supported = set(fact_check.supported_claims)
    for f in findings:
        marker = "[supported]" if f.claim in supported else "[evidence]"
        cites = ", ".join(f.source_ids) or "(none)"
        lines.append(f"- {marker} {f.claim}: {f.evidence[:240]} (sources: {cites})")
    if fact_check.missing_evidence:
        lines.append("")
        lines.append("Known gaps: " + "; ".join(fact_check.missing_evidence))
    return "\n".join(lines)


def _build_sources(sources: list[Source]) -> list[ReportSource]:
    seen: set[str] = set()
    out: list[ReportSource] = []
    for s in sources:
        if s.source_id in seen:
            continue
        seen.add(s.source_id)
        out.append(
            ReportSource(
                source_id=s.source_id, title=s.title, url=s.url, is_demo=s.is_demo
            )
        )
    return out


async def write_report(
    question: str,
    findings: list[Finding],
    sources: list[Source],
    fact_check: FactCheckResult,
    *,
    config: dict[str, Any] | None = None,
) -> ResearchReport:
    """Compose the final grounded report from verified evidence."""

    user = (
        f"Research question:\n{question}\n\n{_render(findings, fact_check)}"
    )
    report = await llm.structured_completion(
        ResearchReport,
        system=SYSTEM_PROMPT,
        user=user,
        agent_name="writer",
        config=config,
    )

    # Enforce grounding: sources come only from collected evidence.
    report = report.model_copy(
        update={
            "sources": _build_sources(sources),
            "confidence": max(0.0, min(1.0, report.confidence)),
        }
    )
    return report
