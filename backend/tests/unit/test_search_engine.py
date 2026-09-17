import uuid
from unittest.mock import MagicMock

from app.search.engine import (
    SearchDocument,
    _make_snippet,
    build_document_for_difference,
    build_document_for_experiment,
    build_document_for_project,
    search,
)
from app.search.provider import SearchProviderError, TfidfSearchProvider


def _doc(entity_type="project", score_text="alpha beta", entity_id=None) -> SearchDocument:
    return SearchDocument(
        entity_type=entity_type,
        entity_id=entity_id or uuid.uuid4(),
        project_id=uuid.uuid4(),
        title="Title",
        text=score_text,
        snippet_source=score_text,
    )


def test_empty_query_short_circuits_without_calling_provider():
    provider = MagicMock()
    result = search("   ", [_doc()], provider, limit=10, offset=0)
    assert result.results == []
    assert result.total == 0
    assert result.provider_name == "none"
    provider.score.assert_not_called()


def test_no_documents_short_circuits_without_calling_provider():
    provider = MagicMock()
    result = search("query", [], provider, limit=10, offset=0)
    assert result.results == []
    provider.score.assert_not_called()


def test_zero_score_documents_are_excluded_not_returned_at_rank_zero():
    provider = MagicMock()
    provider.name = "fake"
    provider.score.return_value = [0.0, 0.9]
    docs = [_doc(), _doc()]
    result = search("query", docs, provider, limit=10, offset=0)
    assert len(result.results) == 1
    assert result.total == 1


def test_results_are_ranked_by_descending_score_and_paginated():
    provider = MagicMock()
    provider.name = "fake"
    docs = [_doc(entity_id=uuid.UUID(int=i)) for i in range(3)]
    provider.score.return_value = [0.1, 0.9, 0.5]

    result = search("query", docs, provider, limit=2, offset=0)
    assert result.total == 3
    assert [r.score for r in result.results] == [0.9, 0.5]

    result_page_2 = search("query", docs, provider, limit=2, offset=2)
    assert [r.score for r in result_page_2.results] == [0.1]


def test_provider_error_falls_back_to_tfidf():
    provider = MagicMock()
    provider.score.side_effect = SearchProviderError("boom")
    docs = [_doc(score_text="matching keyword")]
    result = search("matching", docs, provider, limit=10, offset=0)
    assert result.provider_name == "tfidf-fallback"
    assert len(result.results) == 1


def test_make_snippet_centers_window_on_first_query_token_match():
    text = "x" * 100 + " needle " + "y" * 100
    snippet = _make_snippet(text, "needle", max_len=20)
    assert "needle" in snippet


def test_make_snippet_falls_back_to_prefix_when_no_token_matches():
    text = "abcdefghijklmnopqrstuvwxyz"
    snippet = _make_snippet(text, "notfound", max_len=10)
    assert snippet == text[:10]


def test_make_snippet_empty_text_returns_empty_string():
    assert _make_snippet("", "query") == ""


def test_build_document_for_project_concatenates_fields_and_handles_none():
    project = MagicMock(id=uuid.uuid4(), description=None)
    project.name = "My Project"
    doc = build_document_for_project(project)
    assert doc.entity_type == "project"
    assert doc.title == "My Project"
    assert doc.text == "My Project"
    assert "None" not in doc.text


def test_build_document_for_experiment_concatenates_fields():
    experiment = MagicMock(id=uuid.uuid4(), project_id=uuid.uuid4(), description="does things", workload_type="sklearn_tabular")
    experiment.name = "Exp A"
    doc = build_document_for_experiment(experiment)
    assert doc.entity_type == "experiment"
    assert "Exp A" in doc.text
    assert "does things" in doc.text
    assert "sklearn_tabular" in doc.text


def test_build_document_for_difference_builds_snippet_source():
    difference = MagicMock(
        id=uuid.uuid4(), field="dependency.numpy", old_value="1.24.0", new_value="1.26.0", evidence_source="pip freeze"
    )
    project_id = uuid.uuid4()
    doc = build_document_for_difference(difference, project_id)
    assert doc.entity_type == "difference"
    assert doc.project_id == project_id
    assert "dependency.numpy" in doc.text
    assert doc.snippet_source == "dependency.numpy: 1.24.0 -> 1.26.0"


def test_search_is_deterministic_end_to_end_with_real_tfidf_provider():
    provider = TfidfSearchProvider()
    docs = [
        _doc(entity_id=uuid.UUID(int=1), score_text="numpy dependency version change"),
        _doc(entity_id=uuid.UUID(int=2), score_text="completely unrelated dataset content"),
    ]
    result = search("numpy version", docs, provider, limit=10, offset=0)
    assert result.provider_name == "tfidf"
    assert len(result.results) == 1
    assert result.results[0].entity_id == uuid.UUID(int=1)
