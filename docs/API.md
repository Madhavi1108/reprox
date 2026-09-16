# API

Status: implemented (Phase 19), wiring-tested only — see the Verification
limitation section. No route has ever been exercised against a live
Postgres database.

Spec section 72 (`REPROX.pdf` page 61, verbatim, the complete list):

```
POST /projects            GET /projects
POST /experiments         GET /experiments        GET /experiments/{id}
POST /experiments/{id}/runs                        GET /runs/{id}
POST /runs/{id}/compare                            GET /comparisons/{id}
GET /reproducibility/{id}
GET /provenance/{id}      GET /lineage/{id}
POST /investigations      GET /investigations/{id}
POST /counterfactuals     GET /counterfactuals/{id}
GET /datasets  GET /environments  GET /artifacts
POST /search
GET /jobs  GET /jobs/{id}
GET /reports/{id}
```

## Endpoints built vs. deferred

Only the endpoints backed by phases already in scope are implemented.
`/investigations`, `/counterfactuals` (Phases 22/23), `/datasets`,
`/environments`, `/artifacts` as standalone registries, `/search`
(Phase 25), and `/reports/{id}` (Phase 26) are all `OUT OF SCOPE for MVP`
per the existing tracker — not built here, and not silently missing
either.

**Built** (`app/api/v1/routers/`): `POST/GET /projects`,
`POST/GET /experiments`, `GET /experiments/{id}`,
`POST /experiments/{id}/runs`, `GET /runs/{id}`,
`POST /runs/{id}/compare`, `GET /comparisons/{id}`,
`GET /reproducibility/{id}`, `GET /provenance/{id}`, `GET /lineage/{id}`,
`GET /jobs`, `GET /jobs/{id}`.

**`GET /dashboard`** is also built, even though it's not literally named
in §72 — spec §53 requires "the dashboard must use real backend data"
and names exactly the fields this endpoint returns (project/experiment/
run counts, a reproducibility-classification breakdown, active job
count, recent experiments). Every field is a real query or a Phase 18
tracker read, never a placeholder.

## `GET /reproducibility/{id}` is keyed by `comparison_id`

`ReproducibilityAssessment` is a 1:1 child of `ExperimentComparison` (no
independent natural key a client would know ahead of time) — the `{id}`
path parameter is the comparison's id, which a client already has from
the `POST /runs/{id}/compare`/`GET /comparisons/{id}` response.

## `POST /runs/{id}/compare` accepts inline provenance payloads

No phase before this one persists captured provenance
(`CodeSnapshot`/`DatasetVersion`/`Environment`/`Configuration` rows)
against a real run — only the in-memory Phase 4-8 `capture_*` dataclasses
exist, and they're produced wherever the code/data/environment actually
live (a client-side agent, or the Phase 17 sandbox runner after it
finishes) — never on the API server, which has no access to that
filesystem. So this endpoint accepts each side's provenance as inline
JSON matching each dataclass's field names (`RunProvenanceIn`: `code`,
`dataset`, `environment`, `configuration`, `randomness`, `metrics`,
each optional) rather than looking them up from a DB row that doesn't
exist yet. This is the correct architecture for a distributed system,
not a workaround: the server never re-derives provenance from a
filesystem it doesn't have. A malformed payload (wrong fields for the
dataclass) is rejected with `422 validation_failed`, not a 500.

The endpoint runs the full existing pipeline in one call: Phase 11
(`compare_experiments`) → Phase 12 (`classify_reproducibility`) → Phase
14 (`rank_contributors`) → persists `ExperimentComparison`, `Difference`,
and `ReproducibilityAssessment` rows in one transaction.

## `GET /provenance/{id}` will return an empty graph today

It queries the real `provenance_nodes`/`provenance_edges` tables (Phase
16's schema) — a correct, forward-compatible query — but nothing in the
current pipeline ever writes to those tables (Phase 16's
`assemble_provenance_graph` is only exercised in its own unit tests).
This will return `{"nodes": [], "edges": []}` for every run until a
future phase wires real ingestion. Documented, not a silent surprise.

## `GET /lineage/{id}` is fully live

Unlike `/provenance`, `ExperimentRun.parent_run_id` and
`ExperimentComparison` rows *are* populated by this same API (`POST
/experiments/{id}/runs`, `POST /runs/{id}/compare`), so Phase 15's
`build_lineage_graph`/`ancestors`/`descendants` run against real data.

## `POST /experiments/{id}/runs` triggers real (but unverified) execution

Creates the `ExperimentRun` + a Phase 18 job, then schedules
`app.jobs.orchestrator.execute_experiment_run` as a FastAPI
`BackgroundTasks` callback — real code wiring Phase 17's `SandboxRunner`
to the job's stage transitions, not a stub. It has never run end to end
in this environment (no Docker daemon, no Postgres) — `SandboxRunner`
already degrades to a reported `ERROR` status rather than crashing when
Docker is unreachable, so calling this against no daemon fails
predictably. The job walks the full 9-stage forward pipeline even for a
bare run (`COLLECTING_PROVENANCE`/`CAPTURING_ARTIFACTS`/`COMPARING`/
`ANALYZING`/`GENERATING_REPORT` are no-ops here — no automatic downstream
comparison is triggered by a run in isolation), since Phase 18's state
machine only allows sequential transitions, never skipping ahead.

## Auth

No auth/RBAC scheme is specified anywhere in the spec — checked the full
91-page PDF; the only adjacent requirement is a vague §49 "access
control" bullet under Data Privacy with no concrete design. Per the
project's own approved MVP scoping (`docs/PHASE_TRACKER.md` Phase 29),
`get_current_user_id` (`app/api/deps.py`) fetches-or-creates a single
seeded user rather than implementing real authentication. This is a
project scoping decision, not a spec requirement.

## Error handling, validation, pagination

Reuses the existing `app.core.errors` scaffolding (`NotFoundError` → 404,
`ConflictError` → 409, `ValidationFailedError` → 422, all rendered as
`{"error": {"code", "message", "details"}}` by the already-registered
exception handler) rather than introducing a second error convention.
Pydantic v2 schemas validate every request/response body. List endpoints
return `Page[T]` (`items`, `total`, `limit`, `offset`) with
`limit`/`offset` query parameters (`app.api.deps.PageParams`, default 20,
max 100).

## Verification limitation

**No route in this phase has been exercised against a real Postgres
database.** This environment has no reachable Postgres (same limitation
Phase 17 hit with Docker, Phase 18 hit with its enum migration) — the DB
only runs via `docker-compose.yml`, and Docker isn't available here.

What *is* verified (`backend/tests/unit/test_api_app_wiring.py`): the
FastAPI app assembles without error, every router/schema imports
correctly, `/openapi.json` generates successfully (proving every Pydantic
model and route signature is valid), every spec-required path is
registered, `/health` works (it never touches the DB), a request for a
nonexistent job returns 404 without touching the DB (Phase 18's tracker
is in-process), and Pydantic body validation rejects a malformed request
before the route body runs.

What is **not** verified: that any route successfully reads or writes
real rows, that `IntegrityError` handling in `POST /projects` actually
fires against a real unique-constraint violation, that the
`POST /runs/{id}/compare` → persist → `GET /comparisons/{id}` round-trip
returns what was written, or that `BackgroundTasks` execution against a
real session behaves as expected. Real end-to-end verification needs an
environment with both Postgres and (for the run-execution path) Docker
available — CI, or a developer machine.
