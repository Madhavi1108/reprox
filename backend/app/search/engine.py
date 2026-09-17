"""Search ranking engine (Phase 25).

Pure Python: takes already-fetched `SearchDocument`s (assembled by the
router from ORM rows - the DB coupling stays out of this module, same
split as `app/ai/explainer.py` keeps from `app/ai/provider.py`) and a
`SearchProvider`, and returns a ranked, paginated result set. Never
generates prose - see `app/search/provider.py`'s module docstring.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.search.provider import SearchProvider, SearchProviderError, TfidfSearchProvider

SEARCH_ENGINE_VERSION = "1.0.0"


@dataclass(frozen=True)
class SearchDocument:
    entity_type: str
    entity_id: uuid.UUID
    project_id: uuid.UUID | None
    title: str
    text: str
    snippet_source: str


@dataclass(frozen=True)
class SearchResult:
    entity_type: str
    entity_id: uuid.UUID
    project_id: uuid.UUID | None
    title: str
    snippet: str
    score: float


@dataclass(frozen=True)
class SearchResults:
    results: list[SearchResult]
    total: int
    provider_name: str


def _clean(value: str | None) -> str:
    return value if value else ""


def build_document_for_project(project) -> SearchDocument:
    name = _clean(project.name)
    description = _clean(project.description)
    return SearchDocument(
        entity_type="project",
        entity_id=project.id,
        project_id=project.id,
        title=name,
        text=f"{name} {description}".strip(),
        snippet_source=description or name,
    )


def build_document_for_experiment(experiment) -> SearchDocument:
    name = _clean(experiment.name)
    description = _clean(experiment.description)
    workload_type = _clean(getattr(experiment, "workload_type", None))
    return SearchDocument(
        entity_type="experiment",
        entity_id=experiment.id,
        project_id=experiment.project_id,
        title=name,
        text=f"{name} {description} {workload_type}".strip(),
        snippet_source=description or name,
    )


def build_document_for_difference(difference, project_id: uuid.UUID | None) -> SearchDocument:
    field = _clean(difference.field)
    old_value = _clean(difference.old_value)
    new_value = _clean(difference.new_value)
    evidence_source = _clean(difference.evidence_source)
    return SearchDocument(
        entity_type="difference",
        entity_id=difference.id,
        project_id=project_id,
        title=field,
        text=f"{field} {old_value} {new_value} {evidence_source}".strip(),
        snippet_source=f"{field}: {old_value} -> {new_value}" if field else "",
    )


def _make_snippet(text: str, query: str, max_len: int = 160) -> str:
    if not text:
        return ""

    tokens = [token for token in query.lower().split() if token]
    lowered = text.lower()
    match_pos = -1
    for token in tokens:
        pos = lowered.find(token)
        if pos != -1:
            match_pos = pos
            break

    if match_pos == -1:
        return text[:max_len]

    half = max_len // 2
    start = max(0, match_pos - half)
    end = min(len(text), start + max_len)
    start = max(0, end - max_len)
    return text[start:end]


def search(
    query: str,
    documents: list[SearchDocument],
    provider: SearchProvider,
    limit: int,
    offset: int,
) -> SearchResults:
    stripped = query.strip()
    if not stripped or not documents:
        return SearchResults(results=[], total=0, provider_name="none")

    texts = [doc.text for doc in documents]
    try:
        scores = provider.score(stripped, texts)
        provider_name = provider.name
    except SearchProviderError:
        scores = TfidfSearchProvider().score(stripped, texts)
        provider_name = "tfidf-fallback"

    scored = [(score, doc) for score, doc in zip(scores, documents) if score > 0.0]
    scored.sort(key=lambda pair: (-pair[0], pair[1].entity_type, str(pair[1].entity_id)))

    total = len(scored)
    page = scored[offset : offset + limit]
    results = [
        SearchResult(
            entity_type=doc.entity_type,
            entity_id=doc.entity_id,
            project_id=doc.project_id,
            title=doc.title,
            snippet=_make_snippet(doc.snippet_source, stripped),
            score=round(score, 6),
        )
        for score, doc in page
    ]
    return SearchResults(results=results, total=total, provider_name=provider_name)
