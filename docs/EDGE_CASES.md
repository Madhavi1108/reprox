# Edge Cases (Phase 32, spec-required)

Status: new. Consolidates edge cases already handled and tested per-phase
into one index. Each entry points at the phase doc/test that owns it —
this file doesn't reimplement or re-verify anything, only maps it.

| Edge case | Handling | Where |
|---|---|---|
| Dirty working tree, detached HEAD, shallow clone, no `.git` at all | Each detected explicitly and recorded on `CodeProvenance`, not silently ignored or mistaken for a clean commit | `app/provenance/code.py`, Phase 4 |
| Missing or corrupted dataset file | Raises a specific error rather than a generic exception or a wrong hash | `app/provenance/dataset.py`, Phase 5 |
| Same row count, different content/hash, same schema | Correctly distinguished from a true content match — hash comparison never short-circuits on row count alone | `app/provenance/dataset.py`, Phase 5 |
| Declared-but-unbound stochastic parameter (e.g. `random_state` referenced but never set) | Forces `NON_DETERMINISTIC` rather than defaulting to `DETERMINISTIC` — the classifier never claims determinism it can't prove | `app/provenance/randomness.py`, Phase 8 |
| Both-sides-missing vs. one-side-missing provenance in a comparison | Explicit `NOT_COMPARABLE` (both missing, or version mismatch) vs. `UNKNOWN` (one side missing) — never conflated | `app/comparison/`, Phase 11 |
| Zero-tolerance metric comparison | Both abs/rel tolerance default to `0.0` (exact equality) rather than an arbitrary embedded threshold; per-metric overrides available | `app/comparison/category_comparators/metrics.py`, Phase 13 |
| No metrics captured on either side | `metrics_status` stays `NOT_COMPARABLE` rather than assuming a match | Phase 13 |
| Reproducibility classification with no outcome evidence | Lands on `INSUFFICIENT_EVIDENCE` rather than guessing a classification from setup alone | `app/reproducibility/classifier.py`, Phase 12 |
| Cyclic run-lineage data | `ancestors()`/`descendants()` traversal is cycle-safe | `app/lineage/graph.py`, Phase 15 |
| Empty evidence bundle passed to the AI explainer | Short-circuits to `INSUFFICIENT_EVIDENCE` without ever invoking the provider (no wasted API call, no hallucination risk) | `app/ai/explainer.py`, Phase 24 |
| AI provider response references an evidence ID not in the original bundle | Stripped; degrades to `UNKNOWN` if nothing survives grounding | `app/ai/explainer.py`, Phase 24 |
| Empty semantic-search query | Short-circuits without calling the search provider | `app/search/engine.py`, Phase 25 |
| A comparison with no potential contributor | `POST /investigations` and `POST /counterfactuals` return `422`, not a plan built from nothing | `app/investigation/planner.py`/`counterfactual.py`, Phase 22/23; verified end-to-end in `backend/tests/e2e/test_investigation_and_search_e2e.py`, Phase 31 |
| Unresolvable `investigation_id`/`counterfactual_id` query param on `/reports/{id}` | Soft-fails that one report section (`available: false` + reason) rather than 404ing the whole report | `app/api/v1/routers/reports.py`, Phase 26 |
| Sandbox entrypoint script path traversal / absolute path | Rejected by `SandboxConfigError` before any container starts — POSIX `..`, absolute POSIX, absolute Windows drive letter, UNC path all covered | `app/sandbox/runner.py`, Phase 17; `tests/unit/test_sandbox_security.py`, Phase 29 |
| No Docker daemon reachable | `SandboxRunner` reports `SandboxRunStatus.ERROR` rather than raising/crashing the request | `app/sandbox/runner.py`, Phase 17; confirmed live in Phase 31 (`docs/E2E_TESTING.md`) |
| Excel export with an empty database | All 17 sheets still render, header-only | `app/export/excel.py`, Phase 27; `tests/unit/test_excel_export.py` |
| A project slug collision | `POST /projects` returns `409 Conflict` via a caught `IntegrityError`, not a raw DB error | `app/api/v1/routers/projects.py`, Phase 19 |
