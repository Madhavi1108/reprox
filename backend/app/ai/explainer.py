"""Evidence-grounded AI explanations (Phase 24, spec sections 41/43).

"AI must NOT be the source of truth. AI is an interpretation layer over
structured provenance." The evidence bundle is assembled here, in plain
Python, from already-persisted `Difference`/`ReproducibilityAssessment`
rows - never from anything the model itself asserts. The model (or
`NullProvider`) only gets to phrase what it's handed, and its output is
validated against that same bundle afterward (hallucination control,
spec section 43): any evidence ID it references that isn't in the bundle
is stripped, never trusted.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.ai.provider import AIProvider, AIRequest
from app.db.models.comparison import ExperimentComparison, ReproducibilityAssessment

AI_EXPLAINER_VERSION = "1.0.0"


class ExplanationStatus(str, Enum):
    OK = "OK"
    UNKNOWN = "UNKNOWN"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


@dataclass(frozen=True)
class EvidenceItem:
    id: str
    description: str


@dataclass(frozen=True)
class ExplanationResult:
    status: ExplanationStatus
    text: str
    evidence_ids: list[str]
    provider_name: str


def build_evidence_bundle(
    comparison: ExperimentComparison, reproducibility: ReproducibilityAssessment | None
) -> list[EvidenceItem]:
    items = [
        EvidenceItem(
            id=f"DIFF-{diff.id}",
            description=(
                f"[{diff.category.value}] {diff.field}: {diff.old_value!r} -> {diff.new_value!r} "
                f"(severity={diff.severity.value}, confidence={diff.confidence.value})"
            ),
        )
        for diff in comparison.differences
    ]
    if reproducibility is not None:
        items.append(
            EvidenceItem(
                id=f"CLASSIFICATION-{reproducibility.id}",
                description=f"Reproducibility classification: {reproducibility.classification.value}",
            )
        )
    return items


def _build_prompt(evidence: list[EvidenceItem]) -> str:
    lines = "\n".join(f"{item.id}: {item.description}" for item in evidence)
    return (
        "Summarize this experiment comparison for a scientist reviewing a reproducibility "
        f"failure, using ONLY the following structured evidence:\n{lines}"
    )


def explain_comparison(
    comparison: ExperimentComparison, reproducibility: ReproducibilityAssessment | None, provider: AIProvider
) -> ExplanationResult:
    evidence = build_evidence_bundle(comparison, reproducibility)

    if not evidence:
        return ExplanationResult(
            status=ExplanationStatus.INSUFFICIENT_EVIDENCE,
            text="No structured evidence was available to explain.",
            evidence_ids=[],
            provider_name="none",
        )

    allowed_ids = [item.id for item in evidence]
    request = AIRequest(prompt=_build_prompt(evidence), allowed_evidence_ids=allowed_ids)
    response = provider.generate(request)

    grounded_ids = [eid for eid in response.referenced_evidence_ids if eid in allowed_ids]

    if not grounded_ids:
        return ExplanationResult(
            status=ExplanationStatus.UNKNOWN,
            text="The provider's response could not be grounded in the available evidence.",
            evidence_ids=[],
            provider_name=response.provider_name,
        )

    return ExplanationResult(
        status=ExplanationStatus.OK,
        text=response.text,
        evidence_ids=grounded_ids,
        provider_name=response.provider_name,
    )
