import json
from unittest.mock import MagicMock, patch

import pytest

from app.ai.provider import (
    AIProviderConfig,
    AIProviderError,
    AIRequest,
    ClaudeProvider,
    NullProvider,
    OpenAIProvider,
    get_ai_provider,
)
from app.config import Settings


def _request(**overrides) -> AIRequest:
    kwargs = dict(prompt="Explain this.", allowed_evidence_ids=["DIFF-1", "DIFF-2"])
    kwargs.update(overrides)
    return AIRequest(**kwargs)


def test_null_provider_only_references_given_evidence():
    response = NullProvider().generate(_request())
    assert response.provider_name == "null"
    assert set(response.referenced_evidence_ids) == {"DIFF-1", "DIFF-2"}
    assert "DIFF-1" in response.text
    assert "DIFF-2" in response.text


def test_null_provider_with_no_evidence():
    response = NullProvider().generate(_request(allowed_evidence_ids=[]))
    assert response.referenced_evidence_ids == []
    assert "No structured evidence" in response.text


def test_get_ai_provider_prefers_claude_then_openai_then_null():
    settings = Settings(anthropic_api_key="a-key", openai_api_key="o-key")
    assert isinstance(get_ai_provider(settings), ClaudeProvider)

    settings = Settings(anthropic_api_key=None, openai_api_key="o-key")
    assert isinstance(get_ai_provider(settings), OpenAIProvider)

    settings = Settings(anthropic_api_key=None, openai_api_key=None)
    assert isinstance(get_ai_provider(settings), NullProvider)


def _mock_anthropic_message(payload: dict):
    block = MagicMock()
    block.text = json.dumps(payload)
    message = MagicMock()
    message.content = [block]
    return message


def test_claude_provider_parses_structured_response():
    provider = ClaudeProvider(api_key="fake-key-never-used")
    fake_client = MagicMock()
    fake_client.messages.create.return_value = _mock_anthropic_message(
        {"text": "summary", "referenced_evidence_ids": ["DIFF-1"]}
    )

    with patch("anthropic.Anthropic", return_value=fake_client):
        response = provider.generate(_request(config=AIProviderConfig(max_retries=1)))

    assert response.text == "summary"
    assert response.referenced_evidence_ids == ["DIFF-1"]
    assert response.provider_name == "claude"
    fake_client.messages.create.assert_called_once()


def test_claude_provider_retries_on_malformed_json_then_raises():
    provider = ClaudeProvider(api_key="fake-key-never-used")
    fake_client = MagicMock()
    bad_block = MagicMock()
    bad_block.text = "not json"
    bad_message = MagicMock()
    bad_message.content = [bad_block]
    fake_client.messages.create.return_value = bad_message

    with patch("anthropic.Anthropic", return_value=fake_client):
        with pytest.raises(AIProviderError):
            provider.generate(_request(config=AIProviderConfig(max_retries=2)))

    assert fake_client.messages.create.call_count == 2


def test_claude_provider_passes_timeout_to_client():
    provider = ClaudeProvider(api_key="fake-key-never-used")
    fake_client = MagicMock()
    fake_client.messages.create.return_value = _mock_anthropic_message(
        {"text": "summary", "referenced_evidence_ids": []}
    )

    with patch("anthropic.Anthropic", return_value=fake_client) as mock_ctor:
        provider.generate(_request(config=AIProviderConfig(timeout_seconds=5.0, max_retries=1)))

    _, kwargs = mock_ctor.call_args
    assert kwargs["timeout"] == 5.0


def _mock_openai_response(payload: dict):
    choice = MagicMock()
    choice.message.content = json.dumps(payload)
    response = MagicMock()
    response.choices = [choice]
    return response


def test_openai_provider_parses_structured_response():
    provider = OpenAIProvider(api_key="fake-key-never-used")
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = _mock_openai_response(
        {"text": "summary", "referenced_evidence_ids": ["DIFF-2"]}
    )

    with patch("openai.OpenAI", return_value=fake_client):
        response = provider.generate(_request(config=AIProviderConfig(max_retries=1)))

    assert response.text == "summary"
    assert response.referenced_evidence_ids == ["DIFF-2"]
    assert response.provider_name == "openai"
