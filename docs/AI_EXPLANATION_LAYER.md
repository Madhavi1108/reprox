# AI Explanation Layer

Status: implemented (Phase 24), unit-tested. `NullProvider` is the only
path exercised end-to-end here; `ClaudeProvider`/`OpenAIProvider` are
real code verified only against mocked SDK clients — see Verification
limitation. This phase was a greenfield build: despite the tracker's
prior "AIProvider interface + NullProvider stub only" note, no AI-related
code existed anywhere in the codebase before this phase.

Spec sections 41-43 (`REPROX.pdf` pages 36-38, verbatim):

> **§41 AI COMPONENT** — AI must NOT be the source of truth. AI is an interpretation layer over structured provenance. AI may assist with: experiment summaries, difference explanations, investigation planning, natural-language queries, anomaly interpretation, historical pattern explanation. AI must NEVER invent: experiment runs, metrics, dependencies, code changes, dataset changes, hardware, environment information, causal conclusions.
>
> **§42 AI PROVIDER ABSTRACTION** — Create: AIProvider. Possible implementations: ClaudeProvider, OpenAIProvider, LocalProvider. Support: structured output, retries, timeouts, token limits, schema validation, provider errors, logging without secrets.
>
> **§43 AI HALLUCINATION CONTROL** — AI explanations must only use retrieved structured evidence. Every AI explanation should reference evidence IDs. If evidence is unavailable: UNKNOWN. If evidence is insufficient: INSUFFICIENT_EVIDENCE.

§44 (Natural Language Interface) is Phase 25's "Semantic search" territory
— a query interface, not an explanation generator — and is not built
here.

## Architecture: grounding lives in Python, not the model

The load-bearing design decision, straight from §41: evidence selection
happens entirely in deterministic code (`app/ai/explainer.py`), before
any model is ever called. The model — or `NullProvider`, when none is
configured — only gets to *phrase* a summary of facts it's handed; it
never decides what counts as evidence. This is what makes "AI is an
interpretation layer over structured provenance, not the source of
truth" actually true architecturally, not just asserted.

## `NullProvider` is a real default, not a stub

With no API key configured anywhere in this environment,
`get_ai_provider()` always returns `NullProvider`. It renders the
evidence bundle as a plain list — no model-generated prose — which is
trivially grounded by construction (it can only ever restate what it was
given). This means an "AI explanation" is genuinely available in any
deployment that hasn't wired an LLM key, not an error path. Acceptance
checklist item 27 ("AI explanations are evidence-backed") is satisfied
even in this exact zero-key environment.

## Provider abstraction (`app/ai/provider.py`)

`AIProvider` is a `Protocol` with one method, `generate(AIRequest) -> AIResponse`.
Three implementations:

- `NullProvider` — described above.
- `ClaudeProvider` / `OpenAIProvider` — real implementations against the
  official `anthropic`/`openai` SDKs (added as real dependencies in
  `pyproject.toml`, not dev-only, since these are production code paths).
  Each prompts for a structured JSON response
  (`{"text": ..., "referenced_evidence_ids": [...]}`), retries up to
  `AIProviderConfig.max_retries` on malformed output, and passes
  `timeout_seconds`/`max_tokens` through to the SDK client — the §42
  "retries/timeouts/token limits/schema validation" requirements.
  Logging (`logger.info("ai_provider_request", ...)`) includes only
  provider name, attempt number, and evidence count — never the API key
  or prompt contents ("logging without secrets").
- `LocalProvider` (named in §42) is not implemented — there's no local
  model runtime anywhere in this codebase to wrap, and inventing one
  would be a separate, large infrastructure project, not a small
  addition. `get_ai_provider()`'s selection order (Claude → OpenAI →
  Null) already covers every provider this environment can actually
  reach.

`get_ai_provider(settings)` picks `ClaudeProvider` if `anthropic_api_key`
is set, else `OpenAIProvider` if `openai_api_key` is set, else
`NullProvider` — always `NullProvider` in this environment, since neither
key is configured.

## Hallucination control (`app/ai/explainer.py`)

`explain_comparison(comparison, reproducibility, provider)`:

1. Builds an evidence bundle: one item per `Difference` row (`DIFF-<id>`)
   plus one for the `ReproducibilityAssessment` (`CLASSIFICATION-<id>`).
2. **If the bundle is empty, returns `INSUFFICIENT_EVIDENCE` immediately
   — without ever calling the provider.** Never spend a request (or
   fabricate an explanation) when there's nothing to ground it in.
   Verified directly: `test_empty_evidence_returns_insufficient_evidence_without_calling_provider`
   asserts the mock provider's `generate` was never called.
3. Otherwise, prompts the provider with *only* the bundle's facts and its
   exact allowed evidence IDs, then validates the response: any
   `referenced_evidence_ids` not in the bundle are stripped (never
   trusted, regardless of what the model claims). If every referenced ID
   gets stripped, the result degrades to `UNKNOWN` rather than presenting
   a groundless explanation as legitimate.

Three-value `ExplanationStatus` (`OK`/`UNKNOWN`/`INSUFFICIENT_EVIDENCE`)
mirrors — in spirit, not by literal enum reuse — the same honesty
vocabulary `ComparisonStatus.UNKNOWN`/`ReproducibilityClassification.INSUFFICIENT_EVIDENCE`
already use elsewhere in this codebase.

## API

`POST /api/v1/comparisons/{comparison_id}/explain` — not in spec §72's
literal minimum endpoint list, but required by acceptance checklist item
27, the same "necessary addition" situation as Phase 19's `/dashboard`.

## Verification limitation

`NullProvider` and the full `explain_comparison` grounding/hallucination-
control pipeline are exercised directly (12 new unit tests). `ClaudeProvider`/
`OpenAIProvider` are real, complete implementations but have never made
a live network call in this environment — no API key is configured, and
none should be fabricated to test one. They're verified only against a
mocked SDK client (`unittest.mock.patch("anthropic.Anthropic", ...)` /
`patch("openai.OpenAI", ...)`), confirming the retry/timeout/schema-
validation logic is correct, not that a real Claude or GPT response would
parse as expected.
