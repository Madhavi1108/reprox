"""Search scoring provider abstraction (Phase 25, spec acceptance item 28 /
section 44 "Natural Language Interface").

This is a query interface, not an explanation generator - unlike Phase
24's `AIProvider`, a `SearchProvider` never produces prose. It only scores
how relevant each candidate document is to a free-text query, so the
engine can rank and return structured rows.

No API key is configured anywhere in this environment, so
`OpenAIEmbeddingSearchProvider` has never made a real network call here -
it's tested only against a mocked SDK client (same posture as Phase 24's
`ClaudeProvider`/`OpenAIProvider`). `TfidfSearchProvider` is the one
implementation actually exercised end-to-end, and it is deliberately
useful on its own, not a placeholder: TF-IDF + cosine similarity is a real
lexical relevance measure requiring no new dependency (`numpy` is already
present).

There is deliberately no `ClaudeSearchProvider`: Anthropic has no
first-party embeddings API, unlike its text-generation API used by Phase
24. `get_search_provider` therefore only branches on `openai_api_key`,
never `anthropic_api_key`. See docs/SEMANTIC_SEARCH.md.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Protocol

import numpy as np

from app.config import Settings

logger = logging.getLogger(__name__)

SEARCH_PROVIDER_VERSION = "1.0.0"

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


@dataclass(frozen=True)
class SearchProviderConfig:
    max_retries: int = 2
    timeout_seconds: float = 30.0


class SearchProviderError(Exception):
    pass


class SearchProvider(Protocol):
    name: str

    def score(
        self, query: str, documents: list[str], config: SearchProviderConfig = SearchProviderConfig()
    ) -> list[float]: ...


class TfidfSearchProvider:
    """No network, always available. TF-IDF + cosine similarity computed
    over the batch's own vocabulary (query + documents) - never raises,
    never needs configuration."""

    name = "tfidf"

    def score(
        self, query: str, documents: list[str], config: SearchProviderConfig = SearchProviderConfig()
    ) -> list[float]:
        if not documents:
            return []

        all_texts = [query, *documents]
        tokenized = [_tokenize(text) for text in all_texts]
        vocabulary = sorted({token for tokens in tokenized for token in tokens})
        if not vocabulary:
            return [0.0] * len(documents)

        vocab_index = {token: i for i, token in enumerate(vocabulary)}
        term_freq = np.zeros((len(all_texts), len(vocabulary)))
        for row, tokens in enumerate(tokenized):
            for token in tokens:
                term_freq[row, vocab_index[token]] += 1.0

        doc_freq = np.count_nonzero(term_freq, axis=0)
        idf = np.log((1 + len(all_texts)) / (1 + doc_freq)) + 1.0
        tfidf = term_freq * idf

        query_vector = tfidf[0]
        query_norm = np.linalg.norm(query_vector)
        if query_norm == 0.0:
            return [0.0] * len(documents)

        scores = []
        for row in range(1, len(all_texts)):
            doc_vector = tfidf[row]
            doc_norm = np.linalg.norm(doc_vector)
            if doc_norm == 0.0:
                scores.append(0.0)
                continue
            similarity = float(np.dot(query_vector, doc_vector) / (query_norm * doc_norm))
            scores.append(max(0.0, similarity))
        return scores


class OpenAIEmbeddingSearchProvider:
    name = "openai-embeddings"

    def __init__(self, api_key: str, model: str = "text-embedding-3-small") -> None:
        self._api_key = api_key
        self._model = model

    def score(
        self, query: str, documents: list[str], config: SearchProviderConfig = SearchProviderConfig()
    ) -> list[float]:
        if not documents:
            return []

        import openai

        client = openai.OpenAI(api_key=self._api_key, timeout=config.timeout_seconds)
        last_error: Exception | None = None

        for attempt in range(1, config.max_retries + 1):
            logger.info(
                "search_provider_request",
                extra={"provider": self.name, "attempt": attempt, "document_count": len(documents)},
            )
            try:
                response = client.embeddings.create(model=self._model, input=[query, *documents])
                vectors = [np.array(item.embedding, dtype=float) for item in response.data]
                query_vector = vectors[0]
                query_norm = np.linalg.norm(query_vector)
                if query_norm == 0.0:
                    return [0.0] * len(documents)
                scores = []
                for doc_vector in vectors[1:]:
                    doc_norm = np.linalg.norm(doc_vector)
                    if doc_norm == 0.0:
                        scores.append(0.0)
                        continue
                    similarity = float(np.dot(query_vector, doc_vector) / (query_norm * doc_norm))
                    scores.append(max(0.0, similarity))
                return scores
            except openai.APIError as exc:
                last_error = SearchProviderError(f"OpenAI embeddings API error: {exc}")

        raise last_error or SearchProviderError("OpenAI embedding provider failed with no captured error")


def get_search_provider(settings: Settings) -> SearchProvider:
    if settings.openai_api_key:
        return OpenAIEmbeddingSearchProvider(settings.openai_api_key)
    return TfidfSearchProvider()
