from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.config import Settings
from app.search.provider import (
    OpenAIEmbeddingSearchProvider,
    SearchProviderConfig,
    SearchProviderError,
    TfidfSearchProvider,
    get_search_provider,
)


def test_tfidf_scores_term_overlap_higher_than_no_overlap():
    provider = TfidfSearchProvider()
    scores = provider.score("resnet training", ["resnet training run", "completely unrelated text about cats"])
    assert scores[0] > scores[1]


def test_tfidf_identical_text_scores_near_one():
    provider = TfidfSearchProvider()
    scores = provider.score("gradient boosting classifier", ["gradient boosting classifier"])
    assert scores[0] == pytest.approx(1.0, abs=1e-6)


def test_tfidf_empty_documents_returns_empty_list():
    provider = TfidfSearchProvider()
    assert provider.score("anything", []) == []


def test_tfidf_no_vocabulary_overlap_returns_zero():
    provider = TfidfSearchProvider()
    scores = provider.score("xyzxyz", ["completely different words here"])
    assert scores == [0.0]


def test_tfidf_is_case_insensitive():
    provider = TfidfSearchProvider()
    scores = provider.score("ResNet", ["a document mentioning resnet explicitly"])
    assert scores[0] > 0.0


def _mock_embedding_response(vectors: list[list[float]]):
    response = MagicMock()
    response.data = [MagicMock(embedding=vector) for vector in vectors]
    return response


def test_openai_embedding_provider_scores_via_cosine_similarity():
    provider = OpenAIEmbeddingSearchProvider(api_key="fake-key-never-used")
    fake_client = MagicMock()
    fake_client.embeddings.create.return_value = _mock_embedding_response(
        [[1.0, 0.0], [1.0, 0.0], [0.0, 1.0]]
    )

    with patch("openai.OpenAI", return_value=fake_client):
        scores = provider.score("query", ["identical direction", "orthogonal direction"])

    fake_client.embeddings.create.assert_called_once_with(
        model="text-embedding-3-small", input=["query", "identical direction", "orthogonal direction"]
    )
    assert scores[0] == pytest.approx(1.0, abs=1e-6)
    assert scores[1] == pytest.approx(0.0, abs=1e-6)


def test_openai_embedding_provider_retries_then_raises_search_provider_error():
    provider = OpenAIEmbeddingSearchProvider(api_key="fake-key-never-used")
    fake_client = MagicMock()
    fake_client.embeddings.create.side_effect = openai_api_error()

    with patch("openai.OpenAI", return_value=fake_client):
        with pytest.raises(SearchProviderError):
            provider.score("query", ["doc"], config=SearchProviderConfig(max_retries=2))

    assert fake_client.embeddings.create.call_count == 2


def openai_api_error():
    import openai

    return openai.APIError("boom", httpx.Request("GET", "https://example.invalid"), body=None)


def test_get_search_provider_prefers_openai_then_tfidf():
    settings = Settings(anthropic_api_key=None, openai_api_key="o-key")
    assert isinstance(get_search_provider(settings), OpenAIEmbeddingSearchProvider)

    settings = Settings(anthropic_api_key=None, openai_api_key=None)
    assert isinstance(get_search_provider(settings), TfidfSearchProvider)

    # Anthropic has no embeddings API, so having only anthropic_api_key
    # set must NOT select an OpenAI provider - it falls through to TF-IDF.
    settings = Settings(anthropic_api_key="a-key", openai_api_key=None)
    assert isinstance(get_search_provider(settings), TfidfSearchProvider)
