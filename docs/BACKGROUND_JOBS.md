# Background Jobs

Status: implemented (Phase 18), unit-tested (including async concurrency
behavior), MVP scope.

Spec section 45 (`REPROX.pdf` page 39, verbatim):

> Long-running tasks must not block API requests. Architecture: `HTTP Request → Job → Queue → Worker → Experiment Executor → Provenance Collector → Analysis Engine → Database`. Support: job ID, status, progress, retries, cancellation, timeouts, concurrency limits, idempotency, failure recovery. States: `CREATED, QUEUED, PREPARING, COLLECTING_PROVENANCE, EXECUTING, CAPTURING_ARTIFACTS, COMPARING, ANALYZING, GENERATING_REPORT, COMPLETED, FAILED, CANCELLED`.

Implemented in `app/jobs/tracker.py` (`JOB_TRACKER_VERSION = "1.0.0"`).

## The enum mismatch, and why no migration was written

The `jobs.status` column is a Postgres **native enum** (confirmed in the
Alembic migration: `sa.Enum('CREATED','QUEUED','EXECUTING','COMPLETED','FAILED','CANCELLED', name='jobstatus')`)
— only 6 of the spec's 11 states. Extending it needs a live-database
`ALTER TYPE ... ADD VALUE` migration. This development environment has no
reachable Postgres (the DB only runs via `docker-compose.yml`, and Docker
itself isn't available here — the same limitation `docs/EXECUTION_SANDBOX.md`
already documents for Phase 17). Writing a migration that has never been
run against a real database would be an unverified, risky schema change.

**Decision**: the persisted `JobStatus` column is untouched. The full
11-value spec state machine is tracked as `JobStage` — a plain Python
enum, not a DB column — and only collapsed onto `JobStatus` when
`assemble_job()` builds a persistable row. This continues the tracker's
own pre-existing plan ("in-process asyncio job tracker... documented
substitution") rather than introducing it fresh.

## `JobStage` → `JobStatus` collapse table

| `JobStage` | `JobStatus` |
|---|---|
| `CREATED` | `CREATED` |
| `QUEUED` | `QUEUED` |
| `PREPARING` | `EXECUTING` |
| `COLLECTING_PROVENANCE` | `EXECUTING` |
| `EXECUTING` | `EXECUTING` |
| `CAPTURING_ARTIFACTS` | `EXECUTING` |
| `COMPARING` | `EXECUTING` |
| `ANALYZING` | `EXECUTING` |
| `GENERATING_REPORT` | `EXECUTING` |
| `COMPLETED` | `COMPLETED` |
| `FAILED` | `FAILED` |
| `CANCELLED` | `CANCELLED` |

All 7 "actual work is happening" stages collapse to the DB's single
`EXECUTING` value. `test_stage_to_status_collapse_is_exhaustive_and_correct`
asserts every `JobStage` has an entry — the table can never silently miss
a case as the enum evolves.

## State machine

`JOB_STAGE_TRANSITIONS` encodes the forward pipeline
(`CREATED→QUEUED→PREPARING→COLLECTING_PROVENANCE→EXECUTING→CAPTURING_ARTIFACTS→COMPARING→ANALYZING→GENERATING_REPORT→COMPLETED`)
plus a universal escape to `FAILED`/`CANCELLED` from any non-terminal
stage. The three terminal stages (`COMPLETED`/`FAILED`/`CANCELLED`) have
no outgoing transitions — `transition()` raises
`InvalidJobTransitionError` for anything else, including skipping ahead
in the pipeline or acting on an already-terminal job.

## Spec behaviors: implemented vs. deferred

| Behavior | Status |
|---|---|
| Job ID | `create_job()` returns a `uuid.UUID` |
| Status/stage | `JobRecord.stage`, validated `transition()` |
| Progress | `update_progress()`, validated to `0..100` |
| Retries | `retry()` — valid only from `FAILED`, increments `retry_count`, resets to `QUEUED` |
| Cancellation | `cancel()` — valid from any non-terminal stage |
| Failure recovery | `record_failure()` + `retry()` together |
| Concurrency limits | `async with tracker.slot():` — an `asyncio.Semaphore(max_concurrent)`-backed context manager; verified with a real async test that a `max_concurrent+1`th acquirer blocks until a slot frees |
| Idempotency | `create_job(..., idempotency_key=...)` — a repeated key returns the existing job id instead of creating a duplicate |
| Timeouts | **Partially implemented**: `deadline`/`is_overdue()` *track* whether a job has overrun its budget. *Enforcing* it — actually preempting a running coroutine — needs a live worker loop, which is Phase 19's job (the same tracking-vs-enforcing split `docs/EXECUTION_SANDBOX.md` already draws for Phase 17's own timeout, where enforcement *is* implemented because it's a single synchronous `container.wait(timeout=...)` call, not a distributed loop) |
| Full `HTTP Request → Job → Queue → Worker → ... → Database` pipeline | **Deferred to Phase 19** — wiring a real async worker that walks a job through Phase 17's `SandboxRunner`, provenance capture, comparison, and persistence needs an HTTP/request context and a running service, not just a tracker class |

## Assembly

`assemble_job(job_id) -> Job` builds an unattached ORM row (mirrors
`app.comparison.engine.assemble_comparison`) — no DB session touched
here; wiring persistence is Phase 19's job.
