"""Lightweight heuristic evaluator.

This is a *heuristic* evaluation (``heuristic_evaluation``). It is NOT an
authoritative judge of correctness. It cheaply flags obvious quality gaps
before more expensive model-based evaluation would be applied.
"""

from __future__ import annotations

from backend.app.models.schemas import (
    EvaluationResult,
    FactCheckResult,
    Finding,
    ResearchReport,
    Source,
)


def heuristic_evaluation(
    report: ResearchReport,
    findings: list[Finding],
    sources: list[Source],
    fact_check: FactCheckResult | None,
) -> EvaluationResult:
    """Score completeness, groundedness, and evidence coverage in [0, 1]."""

    notes: list[str] = []
    valid_source_ids = {s.source_id for s in sources}

    # --- completeness -----------------------------------------------------
    completeness = 0.0
    if report.summary.strip():
        completeness += 0.4
    else:
        notes.append("report is missing a summary")
    if report.key_findings:
        completeness += 0.3
    else:
        notes.append("report has no key findings")
    if report.analysis.strip():
        completeness += 0.3
    else:
        notes.append("report is missing detailed analysis")

    # --- groundedness -----------------------------------------------------
    # Every cited source in the report must exist among collected sources.
    cited = {s.source_id for s in report.sources}
    if not cited:
        groundedness = 0.0
        notes.append("report cites no sources")
    else:
        invalid = cited - valid_source_ids
        if invalid:
            notes.append(f"report cites unknown sources: {sorted(invalid)}")
        groundedness = round(len(cited & valid_source_ids) / len(cited), 3)

    # Penalize if unsupported claims exist but confidence is high.
    if fact_check and fact_check.unsupported_claims and report.confidence > 0.7:
        groundedness = max(0.0, groundedness - 0.2)
        notes.append("unsupported claims present despite high confidence")

    # --- evidence coverage ------------------------------------------------
    # Fraction of findings that cite at least one valid source.
    if findings:
        covered = sum(
            1 for f in findings if any(sid in valid_source_ids for sid in f.source_ids)
        )
        evidence_coverage = round(covered / len(findings), 3)
    else:
        evidence_coverage = 0.0
        notes.append("no findings were collected")

    overall = round((completeness + groundedness + evidence_coverage) / 3, 3)

    return EvaluationResult(
        completeness=round(completeness, 3),
        groundedness=groundedness,
        evidence_coverage=evidence_coverage,
        overall=overall,
        notes=notes,
        method="heuristic_evaluation",
    )
