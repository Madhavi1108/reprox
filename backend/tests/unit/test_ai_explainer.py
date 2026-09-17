import uuid
from unittest.mock import MagicMock

from app.ai.explainer import ExplanationStatus, build_evidence_bundle, explain_comparison
from app.ai.provider import AIResponse
from app.db.models.enums import Confidence, DifferenceCategory, DifferenceType, ReproducibilityClassification, Severity


def _diff(category=DifferenceCategory.ENVIRONMENT, field="dependencies.torch"):
    diff = MagicMock()
    diff.id = uuid.uuid4()
    diff.category = category
    diff.field = field
    diff.old_value = "2.5"
    diff.new_value = "2.6"
    diff.difference_type = DifferenceType.VALUE_CHANGED
    diff.severity = Severity.HIGH
    diff.confidence = Confidence.MEDIUM
    return diff


def _comparison(differences=None):
    comparison = MagicMock()
    comparison.differences = differences or []
    return comparison


def _reproducibility():
    assessment = MagicMock()
    assessment.id = uuid.uuid4()
    assessment.classification = ReproducibilityClassification.NOT_REPRODUCIBLE
    return assessment


def test_build_evidence_bundle_includes_differences_and_classification():
    diff = _diff()
    bundle = build_evidence_bundle(_comparison([diff]), _reproducibility())
    ids = [item.id for item in bundle]
    assert f"DIFF-{diff.id}" in ids
    assert any(i.startswith("CLASSIFICATION-") for i in ids)


def test_empty_evidence_returns_insufficient_evidence_without_calling_provider():
    provider = MagicMock()
    result = explain_comparison(_comparison([]), None, provider)

    assert result.status == ExplanationStatus.INSUFFICIENT_EVIDENCE
    assert result.evidence_ids == []
    provider.generate.assert_not_called()


def test_grounded_response_passes_through():
    diff = _diff()
    comparison = _comparison([diff])
    provider = MagicMock()
    provider.generate.return_value = AIResponse(
        text="The torch version changed.", referenced_evidence_ids=[f"DIFF-{diff.id}"], provider_name="null"
    )

    result = explain_comparison(comparison, None, provider)

    assert result.status == ExplanationStatus.OK
    assert result.evidence_ids == [f"DIFF-{diff.id}"]
    assert result.text == "The torch version changed."


def test_hallucinated_evidence_ids_are_stripped():
    diff = _diff()
    comparison = _comparison([diff])
    provider = MagicMock()
    provider.generate.return_value = AIResponse(
        text="Mentions something fake.",
        referenced_evidence_ids=[f"DIFF-{diff.id}", "DIFF-doesnotexist"],
        provider_name="null",
    )

    result = explain_comparison(comparison, None, provider)

    assert result.status == ExplanationStatus.OK
    assert result.evidence_ids == [f"DIFF-{diff.id}"]


def test_fully_hallucinated_response_degrades_to_unknown():
    diff = _diff()
    comparison = _comparison([diff])
    provider = MagicMock()
    provider.generate.return_value = AIResponse(
        text="Entirely made up.", referenced_evidence_ids=["DIFF-doesnotexist"], provider_name="null"
    )

    result = explain_comparison(comparison, None, provider)

    assert result.status == ExplanationStatus.UNKNOWN
    assert result.evidence_ids == []
