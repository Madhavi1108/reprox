# Security Model (Phase 29)

Status: implemented, **REDUCED SCOPE**, unit-tested.

This document is named in the spec's own Phase-0 required-documentation
list (`REPROX.pdf`, "80. PHASE 0 - ARCHITECTURE & PLANNING") but was
never written until this phase - every other required doc
(`docs/API.md`, `docs/FRONTEND.md`, etc.) was produced alongside its
corresponding phase; this one closes that gap alongside the deferred
security test coverage recorded in `docs/PHASE_TRACKER.md` row 29.

## Spec requirements (verbatim)

> §47 SECURITY - Protect against: arbitrary code execution, command
> injection, path traversal, malicious repositories, malicious datasets,
> zip bombs, oversized artifacts, dependency attacks, secret leakage,
> container escape, SSRF, SQL injection, XSS, unsafe AI output, prompt
> injection, resource exhaustion. Treat source code, README, notebooks,
> configuration, datasets, logs, experiment descriptions as untrusted
> input.

> §73 TESTING (security-tests subset) - Test: path traversal, command
> injection, malicious input, oversized files, prompt injection, secret
> leakage, unauthorized access.

## Threat-by-threat status

| Threat | Status | Mitigation / reason |
|---|---|---|
| Arbitrary code execution | Mitigated | Phase 17's `SandboxRunner` (`app/sandbox/runner.py`) runs all experiment code inside an isolated Docker container - never on the host. |
| Container escape | Partially mitigated | Read-only root filesystem, network disabled by default, mem/CPU/pids limits, empty container environment. Never exercised against a real Docker daemon in this dev environment (same gap Phase 17's own docs already state) - only unit-tested against a mocked client. |
| Path traversal | Mitigated, tested | `SandboxRunner._validate_request` rejects absolute paths and `..` segments in `entrypoint_script`. Tested in `tests/unit/test_sandbox_runner.py` (`test_config_error_for_absolute_entrypoint_script`, `test_config_error_for_path_traversal_entrypoint_script`). |
| Command injection | Mitigated, tested | The Docker command is built as an argv list (`["python", f"/workload/{script}"]`), passed directly to `exec()` - never through a shell - so shell metacharacters in a filename are inert. Tested in `tests/unit/test_security.py::test_shell_metacharacters_in_entrypoint_are_never_shell_interpreted`. |
| Malicious repositories | Partially mitigated | Phase 4's code provenance capture only reads file content/hashes it never executes anything from a repository. |
| Malicious datasets / malicious input | Mitigated, tested | `app/provenance/dataset.py` raises `DatasetParseError`/`DatasetFileNotFoundError` on corrupted or missing files rather than silently succeeding. Tested in `tests/unit/test_dataset_fingerprint.py` (`test_corrupted_dataset_raises_parse_error`, `test_missing_dataset_file_raises_not_fabricates`). |
| Zip bombs / oversized artifacts / oversized files | **Deferred** | No size cap exists anywhere in dataset/artifact capture. `capture_dataset_provenance` streams the content hash in bounded chunks, but then loads the full file via `pandas` for schema/stats with no limit. A real fix touches Phase 5's fingerprinting behavior and its existing test suite - out of scope for this "test and document" pass. |
| Dependency attacks | **Deferred** | No dependency-pinning/scanning story exists. Partially bounded by the sandbox's resource limits, which limit blast radius but don't detect a compromised dependency. |
| Secret leakage | Mitigated, tested | `app/ai/provider.py`'s `logger.info(...)` calls only ever log `provider`/`attempt`/`evidence_count` - never the API key. `SandboxRunner` passes `environment={}` to every container (never forwards host secrets). Tested in `tests/unit/test_security.py::test_api_key_never_appears_in_logs_on_success` / `..._on_provider_error`. |
| SSRF | Not applicable | Confirmed by source search: no outbound HTTP call anywhere in the backend takes a caller-controlled URL - the AI/search providers call fixed Anthropic/OpenAI SDK endpoints only. |
| SQL injection | Mitigated, tested | Confirmed by source search: the only raw SQL in the codebase is a literal `SELECT 1` health check (`app/main.py`); every other query goes through SQLAlchemy's parameterized `.query()`/`.filter()`. A regression guard (`tests/unit/test_security.py::test_no_raw_sql_built_from_string_interpolation_exists`) fails if a future phase ever introduces string-interpolated SQL. |
| XSS | Not applicable | Confirmed by source search: no `dangerouslySetInnerHTML` (or equivalent) anywhere in `frontend/` - React's default JSX escaping is the only exposure and needs no additional code. |
| Unsafe AI output | Partially mitigated | Phase 24's `explain_comparison()` strips any `referenced_evidence_ids` the model cites that aren't in the real evidence bundle, degrading to `UNKNOWN` if nothing survives - the model can never fabricate evidence that appears grounded. |
| Prompt injection | Partially mitigated | `app/ai/explainer.py` embeds `Difference.old_value`/`new_value` (attacker-influenceable dataset/config content) directly into the LLM prompt - a real residual surface. The existing defense is post-hoc, not input sanitization: evidence-ID grounding (above) bounds what the response can *cite* even when evidence content contains an injected instruction. Tested explicitly against adversarial-shaped input in `tests/unit/test_security.py::test_injected_instruction_in_evidence_cannot_smuggle_fake_evidence_ids`. Full content sanitization of evidence text is **not** implemented. |
| Resource exhaustion | Partially mitigated | Phase 17's sandbox enforces mem/CPU/pids limits and an execution timeout. No API-level rate limiting exists (no auth model to rate-limit against - see "Unauthorized access" below). |
| Unauthorized access | **Accepted MVP gap, documented** | `app/api/deps.py`'s `get_current_user_id` takes no caller-supplied identity at all - it always resolves the single seeded user. No auth/RBAC scheme is specified anywhere in the spec (checked the full PDF - only a vague §49 "access control" bullet under Data Privacy, with no concrete design given). Tested as a checkable fact, not a gap papered over, in `tests/unit/test_security.py::test_current_user_dependency_takes_no_caller_controlled_identity` / `..._always_resolves_the_same_seeded_user`. |

## What `test_security.py` covers vs. what's covered elsewhere

Per spec §73's 7-item security-test list:

- **path traversal** → already covered by `tests/unit/test_sandbox_runner.py` (Phase 17) - not duplicated here.
- **malicious input** → already covered by `tests/unit/test_dataset_fingerprint.py` (Phase 5) - not duplicated here.
- **command injection**, **secret leakage**, **prompt injection**, **unauthorized access**, **SQL injection** → new tests in `tests/unit/test_security.py` (this phase).
- **oversized files** → deferred (see table above); no test exists because no mitigation exists yet, and a test that only asserts "no cap" would be documentation, not verification.

## Deferred (explicit, not silently dropped)

- Zip bombs / oversized files: no size cap in dataset/artifact capture.
- Full prompt-injection content sanitization: current defense is
  evidence-ID grounding only, not filtering of injected text in the
  prompt itself.
- Real Docker-daemon verification of sandbox isolation: no reachable
  Docker daemon in this dev environment (same gap as Phase 17).
- Dependency scanning / supply-chain attack detection.
- Multi-user auth / RBAC: no spec requirement exists to build against.

## Verification

`pytest tests/unit` runs all security tests as part of the standard unit
suite - there is no separate security test runner, consistent with how
every other cross-cutting concern in this codebase (benchmarking,
reporting) is verified through the same suite rather than a bespoke
script.
