# Privacy Model (Phase 32, spec-required)

Status: new. Reflects the spec's §49 "access control"/data-handling
concerns as actually implemented, not a generic privacy policy template.

## What data REPROX stores

- **Experiment/project metadata**: names, slugs, descriptions, timestamps
  (`app/db/models/core.py`).
- **Provenance hashes, not raw content**: `app/provenance/*.py`'s
  capture functions compute content hashes (SHA-256) and structural
  metadata (schema, dependency versions, git commit SHA) — they do not
  copy raw dataset rows or full source files into the database. The one
  exception is the client-supplied inline provenance payload accepted by
  `POST /runs/{id}/compare` (`app/schemas/comparison.py`'s
  `RunProvenanceIn`): whatever a caller includes there (e.g. a metric
  value, a config field's literal value) is stored as-is in `Difference.
  old_value`/`new_value`, because comparing requires showing the actual
  differing values — this is inherent to the feature, not incidental
  data collection.
- **One user record**: `app/db/models/core.py`'s `User` — a single
  seeded row (`dev@reprox.local`, `app/api/deps.py`), not real end-user
  accounts. There is no multi-tenant data model to isolate, because
  there is exactly one tenant.

## Third-party data flows

There is exactly one: **Phase 24's AI explanation layer**
(`app/ai/provider.py`, `app/ai/explainer.py`). When `ANTHROPIC_API_KEY`
or `OPENAI_API_KEY` is configured, `POST /api/v1/comparisons/{id}/explain`
sends the comparison's evidence bundle (classification, per-category
comparison statuses, and each `Difference`'s field/old_value/new_value —
`app/ai/explainer.py:_build_prompt`) as plain text to the Claude or
OpenAI API. `NullProvider` is the default in any unconfigured deployment
(including this one) and makes zero network calls — no data leaves the
process unless an operator explicitly configures a key.

**Phase 25's `OpenAIEmbeddingSearchProvider`** similarly sends free-text
document content (project/experiment names+descriptions, difference
field/value text — `app/search/engine.py`) to OpenAI's embeddings API
when configured; `TfidfSearchProvider` (the default, `app/search/
provider.py`) is fully local and makes no network calls.

No other outbound network call exists anywhere in `backend/app/`.

## Secrets

`app/config.py`'s `Settings` holds `anthropic_api_key`/`openai_api_key`/
`database_url` as plain strings. Phase 29's security review
(`docs/SECURITY_MODEL.md`) confirms these are never written to logs
(`app/ai/provider.py`'s `logger.info` calls log only provider
name/attempt/evidence-count, never the key or request body) — this is a
checked, tested fact (`tests/unit/test_security.py`), not an assertion.

## What's explicitly not addressed

No formal data-retention policy, no user-initiated data deletion/export
flow (GDPR-style "right to be forgotten"), and no encryption-at-rest
configuration beyond whatever the deployed Postgres instance itself
provides — all reasonable next steps for a real multi-tenant deployment,
none of them meaningful for a single-seeded-user MVP that has never run
against production data. See `docs/OUT_OF_SCOPE.md`.
