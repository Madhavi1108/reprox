# Semantic Search

Status: implemented (Phase 25), unit-tested. `TfidfSearchProvider` is the
only path exercised end-to-end here; `OpenAIEmbeddingSearchProvider` is
real code verified only against a mocked SDK client — see Verification
limitation. This phase reverses the tracker's prior "OUT OF SCOPE for
MVP" note ("Deferred; only structured filtering via normal API query
params"), the same situation as Phases 22/23: explicitly requested at
full depth despite the earlier deferral.

## Spec grounding

Acceptance checklist item 28 (`pages_out.txt`, extracted from
`REPROX.pdf`), verbatim:

> 28. Natural-language experiment search works.

`docs/AI_EXPLANATION_LAYER.md` already quotes §41 verbatim, which lists
"natural-language queries" as one of AI's permitted assistive roles and
explicitly carves out §44 (Natural Language Interface) as "Phase 25's
'Semantic search' territory — a query interface, not an explanation
generator."

The extraction in `pages_out.txt` also has a section header, `40.
HISTORICAL EXPERIMENT SEARCH`, but its body text is missing from the
extraction — the captured pages jump directly from page 34 (where the
header appears) to page 50. §44's full body text is likewise not present
anywhere in the extraction. **Neither is quoted here beyond their
headers/titles**, consistent with how every other phase doc in this repo
handles spec text that isn't actually recoverable — nothing below is a
fabricated quote.

## Query interface, not an explanation generator

Unlike Phase 24's AI explanation layer, this endpoint never generates
prose and has no hallucination-control pipeline to speak of — there is
nothing to hallucinate. It ranks existing, verbatim DB rows against a
free-text query and returns them as structured JSON. The "AI" in this
phase, when a real embedding provider is configured, is used purely as a
relevance-scoring signal, never as a text generator.

## Corpus

| entity_type | model | fields concatenated for scoring | field used for the displayed snippet |
|---|---|---|---|
| `project` | `Project` | `name`, `description` | `description` (falls back to `name`) |
| `experiment` | `Experiment` | `name`, `description`, `workload_type` | `description` (falls back to `name`) |
| `difference` | `Difference` | `field`, `old_value`, `new_value`, `evidence_source` | `"{field}: {old_value} -> {new_value}"` |

Deliberately **not** indexed in this phase, with reasons:

- `ExperimentRun` — its only free text is `error_message` (usually null or
  short); `status`/`run_type` are enums, already filterable via structured
  query params (the pre-Phase-25 status quo this phase is now adding to,
  not replacing).
- `ReproducibilityAssessment` — `rationale_json` is structured JSON, not
  prose; re-serializing it into a search document is a real feature that
  can be added later without an API break, not an oversight now.
- `Dependency` / `CodeSnapshot` — thin (`package_name`/`version`) or
  rarely populated (`notes`) free text; low value relative to the added
  corpus-building complexity for a first cut.

## Scoring abstraction (`app/search/provider.py`)

`SearchProvider` is a `Protocol` with one method,
`score(query, documents, config) -> list[float]` — deliberately narrower
than Phase 24's `AIProvider.generate`, since scoring is the only operation
this phase needs.

- **`TfidfSearchProvider`** (`name = "tfidf"`) — the `NullProvider` analog:
  always available, no new dependency. Tokenizes the query and every
  document, builds TF-IDF vectors over the batch's own vocabulary, and
  scores by cosine similarity. `numpy` (already a dependency) does the
  vector arithmetic; no `scikit-learn`/`sentence-transformers`/`faiss`
  was added, since TF-IDF + cosine similarity needs neither. Never raises
  — an empty vocabulary or no term overlap just scores everything `0.0`.
- **`OpenAIEmbeddingSearchProvider`** (`name = "openai-embeddings"`) —
  calls `openai.OpenAI(...).embeddings.create(model="text-embedding-3-small", input=[query, *documents])`,
  retrying up to `SearchProviderConfig.max_retries` on `openai.APIError`
  before raising `SearchProviderError`, then scores by cosine similarity
  over the returned embedding vectors — the same retry/timeout shape as
  Phase 24's `OpenAIProvider.generate`.
- **No Claude-based provider.** Anthropic has no first-party embeddings
  API, unlike its text-generation API (used by Phase 24's
  `ClaudeProvider`). `get_search_provider(settings)` therefore only
  branches on `openai_api_key` — an `anthropic_api_key` alone does **not**
  select an OpenAI-embeddings provider; it falls through to
  `TfidfSearchProvider`. This asymmetry is tested explicitly
  (`test_get_search_provider_prefers_openai_then_tfidf`).
- **Fallback on provider error**: if a configured real provider's
  `.score()` raises `SearchProviderError` at query time (e.g. the OpenAI
  API is down or misconfigured), `app/search/engine.py`'s `search()`
  catches it and falls back to a fresh `TfidfSearchProvider()` rather than
  returning a 500 — the result's `provider_name` becomes
  `"tfidf-fallback"` so callers can tell the difference. Same "always
  produce a usable answer" posture as `NullProvider` being a genuine
  default rather than a stub.

No API key is configured anywhere in this environment, so
`get_search_provider()` always returns `TfidfSearchProvider` here — the
one path actually exercised end-to-end.

## Ranking engine (`app/search/engine.py`)

`search(query, documents, provider, limit, offset) -> SearchResults`:

1. An empty or whitespace-only query returns an empty result set
   immediately, **without ever calling the provider** — verified directly
   (`test_empty_query_short_circuits_without_calling_provider`), the same
   short-circuit discipline as Phase 24's `explain_comparison` on empty
   evidence.
2. Documents scoring `0.0` or below are excluded entirely rather than
   returned at rank with a zero score — "no results" means an actually
   empty list, not an unranked dump of the whole corpus.
3. Remaining matches are sorted by descending score, then by
   `(entity_type, entity_id)` as a deterministic tie-break, then sliced by
   `limit`/`offset`. `total` is the match count *before* slicing.
4. `_make_snippet` returns a window of the entity's snippet-source field
   centered on the first case-insensitive query-token match, or a
   truncated prefix if no token matches, or `""` for empty text.

## API

`GET /api/v1/search?q=<text>&limit=&offset=` — not in spec §72's literal
minimum endpoint list, but required by acceptance checklist item 28, the
same "necessary addition" situation as Phase 19's `/dashboard` and Phase
24's `/explain`.

- `q` is `Query(..., min_length=1, max_length=500)`: a genuinely missing
  or empty-string `q` is rejected with **422** by FastAPI's own
  validation, before the endpoint body (and its DB queries) ever runs.
- A `q` that is non-empty but *whitespace-only* (e.g. `"%20"`) passes that
  validation but is caught by `search()`'s empty-query short-circuit,
  returning **200** with `{"items": [], "total": 0, ...}` — "no results"
  is a valid, expected response shape, not an error.
- Response body reuses the existing generic `Page[SearchResultRead]`
  envelope (`items`, `total`, `limit`, `offset`) — no new pagination
  schema was introduced. Each item: `entity_type`, `entity_id`,
  `project_id` (nullable), `title`, `snippet`, `score`.
- No `get_current_user_id` dependency: like `GET /projects` and every
  other list endpoint in this single-seeded-user MVP
  (`app/api/deps.py`), search results are not scoped per user. This is a
  known non-scope, documented rather than silently omitted — real
  multi-tenant search isolation is out of scope for the MVP, same as the
  rest of the API.

## What we deliberately did not build, and why

- **No vector database / ANN index.** The corpus is rebuilt with a linear
  scan on every request (three plain queries against `Project`,
  `Experiment`, `Difference`). This is fine at the data volumes this MVP
  actually has and stops scaling well past a few thousand documents —
  the point at which a real index (pgvector, a dedicated ANN library)
  would become necessary. Building one now would be premature
  infrastructure for data that doesn't exist yet.
- **No persisted search index.** Documents are assembled fresh from live
  DB rows on every request rather than indexed ahead of time. Results are
  therefore always consistent with the database at zero staleness cost,
  at the price of O(corpus) work per query — an explicit trade-off, not
  an oversight.
- **No query understanding / intent classification.** `q` is treated as a
  flat bag of tokens; there's no attempt to detect entity-type filters,
  date ranges, or boolean operators embedded in the query text. Item 28
  ("natural-language experiment search works") is satisfied by ranking
  free text against free text, not by a full NL-to-structured-query
  layer.
- **No cross-entity relevance blending beyond raw score.** All three
  entity types are scored on the same scale and merged into one ranked
  list; there's no per-type boosting (e.g. always ranking a matching
  `Project` above a matching `Difference`).

## Verification limitation

`TfidfSearchProvider` and the full `search()` ranking/pagination/snippet
pipeline are exercised directly and fully (21 new unit tests: 9 in
`test_search_provider.py`, 12 in `test_search_engine.py`).
`OpenAIEmbeddingSearchProvider` is a real, complete implementation but has
never made a live network call in this environment — no API key is
configured, and none should be fabricated to test one. It's verified only
against a mocked `openai.OpenAI` client (`patch("openai.OpenAI", ...)`),
confirming the retry/cosine-similarity logic is correct, not that a real
OpenAI embeddings response would score as expected. Full backend unit
suite: 254/254 green.
