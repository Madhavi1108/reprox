"""AI provider abstraction (Phase 24, spec section 42).

"Create: AIProvider. Possible implementations: ClaudeProvider,
OpenAIProvider, LocalProvider. Support: structured output, retries,
timeouts, token limits, schema validation, provider errors, logging
without secrets."

No API key is configured anywhere in this environment, so `ClaudeProvider`/
`OpenAIProvider` have never made a real network call here - they're
tested only against a mocked SDK client (same posture as Phase 17's
`SandboxRunner` against a mocked Docker client). `NullProvider` is the
one implementation actually exercised end-to-end, and it is deliberately
useful on its own, not a placeholder: it renders a deterministic
template directly from the evidence bundle it's given, so an
explanation is always available even with zero AI infrastructure
configured. See docs/AI_EXPLANATION_LAYER.md.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Protocol

from app.config import Settings

logger = logging.getLogger(__name__)

AI_PROVIDER_VERSION = "1.0.0"


@dataclass(frozen=True)
class AIProviderConfig:
    max_retries: int = 2
    timeout_seconds: float = 30.0
    max_tokens: int = 1024


class AIProviderError(Exception):
    pass


class AIProviderNotConfiguredError(AIProviderError):
    pass


@dataclass(frozen=True)
class AIRequest:
    prompt: str
    # The complete set of evidence IDs the response is allowed to
    # reference - anything else in the response is a hallucination,
    # caught by app.ai.explainer's validation step, not here.
    allowed_evidence_ids: list[str]
    config: AIProviderConfig = field(default_factory=AIProviderConfig)


@dataclass(frozen=True)
class AIResponse:
    text: str
    referenced_evidence_ids: list[str]
    provider_name: str


class AIProvider(Protocol):
    def generate(self, request: AIRequest) -> AIResponse: ...


class NullProvider:
    """No network, always available. Renders the evidence bundle as a
    plain-language list rather than model-generated prose - genuinely
    evidence-grounded by construction, since it only ever restates what
    it was given."""

    name = "null"

    def generate(self, request: AIRequest) -> AIResponse:
        if not request.allowed_evidence_ids:
            text = "No structured evidence was available to explain."
        else:
            text = "Evidence-based summary:\n" + "\n".join(f"- {eid}" for eid in request.allowed_evidence_ids)
        return AIResponse(text=text, referenced_evidence_ids=list(request.allowed_evidence_ids), provider_name=self.name)


def _extract_structured_json(raw_text: str) -> dict:
    import json

    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise AIProviderError(f"provider returned non-JSON output: {exc}") from exc
    if "text" not in parsed or "referenced_evidence_ids" not in parsed:
        raise AIProviderError("provider response missing required fields 'text'/'referenced_evidence_ids'")
    return parsed


def _structured_prompt(request: AIRequest) -> str:
    return (
        f"{request.prompt}\n\n"
        "Respond with ONLY a JSON object of the exact shape "
        '{"text": string, "referenced_evidence_ids": string[]}. '
        f"You may only reference these evidence IDs: {request.allowed_evidence_ids}. "
        "Never mention any run, metric, dependency, code change, dataset, hardware, "
        "environment detail, or causal conclusion that is not explicitly listed above."
    )


class ClaudeProvider:
    name = "claude"

    def __init__(self, api_key: str, model: str = "claude-sonnet-5") -> None:
        self._api_key = api_key
        self._model = model

    def generate(self, request: AIRequest) -> AIResponse:
        import anthropic

        client = anthropic.Anthropic(api_key=self._api_key, timeout=request.config.timeout_seconds)
        last_error: Exception | None = None

        for attempt in range(1, request.config.max_retries + 1):
            logger.info(
                "ai_provider_request", extra={"provider": self.name, "attempt": attempt, "evidence_count": len(request.allowed_evidence_ids)}
            )
            try:
                message = client.messages.create(
                    model=self._model,
                    max_tokens=request.config.max_tokens,
                    messages=[{"role": "user", "content": _structured_prompt(request)}],
                )
                raw_text = "".join(block.text for block in message.content if hasattr(block, "text"))
                parsed = _extract_structured_json(raw_text)
                return AIResponse(
                    text=parsed["text"], referenced_evidence_ids=list(parsed["referenced_evidence_ids"]), provider_name=self.name
                )
            except anthropic.APIError as exc:
                last_error = AIProviderError(f"Claude API error: {exc}")
            except AIProviderError as exc:
                last_error = exc

        raise last_error or AIProviderError("Claude provider failed with no captured error")


class OpenAIProvider:
    name = "openai"

    def __init__(self, api_key: str, model: str = "gpt-5") -> None:
        self._api_key = api_key
        self._model = model

    def generate(self, request: AIRequest) -> AIResponse:
        import openai

        client = openai.OpenAI(api_key=self._api_key, timeout=request.config.timeout_seconds)
        last_error: Exception | None = None

        for attempt in range(1, request.config.max_retries + 1):
            logger.info(
                "ai_provider_request", extra={"provider": self.name, "attempt": attempt, "evidence_count": len(request.allowed_evidence_ids)}
            )
            try:
                response = client.chat.completions.create(
                    model=self._model,
                    max_tokens=request.config.max_tokens,
                    messages=[{"role": "user", "content": _structured_prompt(request)}],
                )
                raw_text = response.choices[0].message.content or ""
                parsed = _extract_structured_json(raw_text)
                return AIResponse(
                    text=parsed["text"], referenced_evidence_ids=list(parsed["referenced_evidence_ids"]), provider_name=self.name
                )
            except openai.APIError as exc:
                last_error = AIProviderError(f"OpenAI API error: {exc}")
            except AIProviderError as exc:
                last_error = exc

        raise last_error or AIProviderError("OpenAI provider failed with no captured error")


def get_ai_provider(settings: Settings) -> AIProvider:
    if settings.anthropic_api_key:
        return ClaudeProvider(settings.anthropic_api_key)
    if settings.openai_api_key:
        return OpenAIProvider(settings.openai_api_key)
    return NullProvider()
