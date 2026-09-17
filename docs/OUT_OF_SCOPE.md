# Out of Scope (Phase 32, spec-required)

Every phase in this build either did the full spec depth or explicitly
scoped down and said so in `docs/PHASE_TRACKER.md`/its own phase doc.
This file is a single consolidated index of everything currently
deferred, each a one-line pointer — the reasoning lives at the source,
not repeated here.

## Infrastructure this dev environment never had

- **Reachable Postgres.** Every DB-touching phase (2, 15-19, 22-31) notes
  this. Phase 31 closed the gap for plain DB-backed flows using an
  in-memory SQLite substitute (`docs/E2E_TESTING.md`); real Postgres-only
  behavior (constraint wording, concurrency semantics) is still
  unverified.
- **Reachable Docker daemon for the sandbox's real image.** Phase 17's
  `SandboxRunner` is only unit-tested against a mocked client; Phase 31
  confirmed Docker itself *is* reachable in this environment but the
  `reprox-sklearn-runner:latest` image was never built/verified against a
  real run (`docs/EXECUTION_SANDBOX.md`, `docs/E2E_TESTING.md`).
- **A live frontend+backend+browser** for real E2E — Playwright/browser
  automation was never run (`docs/E2E_TESTING.md`).

## Explicitly descoped features

- **Auth/RBAC** — single seeded user, `app/api/deps.py` (Phase 19). The
  spec has no auth/RBAC section; this is a project scoping choice.
- **Real dataset/code/environment persistence** — Phase 2's tables exist,
  but no phase writes to them from a live pipeline; provenance is
  accepted inline at compare-time instead (Phase 19).
- **Pipeline and Data-Splits comparison** — no `Pipeline`/`DataSplit`
  model or comparator exists anywhere in the schema (Phase 21).
- **`MODIFIES`/`COUNTERFACTUAL_OF`/`VALIDATES` lineage edges** — need
  controlled-rerun infrastructure beyond Phase 22/23's plan-generation-
  only scope (Phase 15).
- **7 of the spec's 13 provenance-graph entity types** — no defined edge
  exists for them in the spec's own relationship list (Phase 16).
- **Automated controlled-rerun execution** for investigations/
  counterfactuals — Phase 22/23 generate plans and evaluate caller-
  supplied results; they don't execute a parameterized rerun themselves.
- **4 of the spec's 8 named benchmark experiments** (dependency drift,
  randomness, code, multiple-simultaneous) and the full 19-dimension
  synthetic dataset generator (Phase 28).
- **Persistent/incremental TF-IDF index** — `TfidfSearchProvider` refits
  its vocabulary per query; fine at MVP corpus sizes (Phase 25, Phase 30).
- **Chunked dataset-stats computation** — hashing is streamed, but
  `pd.read_csv()` still loads a full dataset for schema/stats (Phase 30).
- **Unfiltered full-DB Excel export stays unfiltered** — an intentional
  Phase 27 design choice, not revisited in Phase 30.
- **Zip-bomb/oversized-file guards and full prompt-injection content
  sanitization** — named explicitly as deferred in Phase 29's threat
  model (`docs/SECURITY_MODEL.md`).
- **Dependency vulnerability scanning and rate limiting** — Phase 29.
- **Real load/scale/stress testing and query-latency measurement** —
  needs the reachable Postgres/Docker this environment doesn't have
  (Phase 30, `docs/EVALUATION_PLAN.md`).
- **Whole-app Docker deployment** (backend/frontend images, a compose
  service for the API) — only Postgres and the sandbox workload image
  are containerized today (`docs/DEPLOYMENT.md`).

Nothing above is silently missing — every item is a decision recorded at
the phase that made it, cross-referenced here so the full picture is in
one place.
