---
tags:
  - '#audit'
  - '#cli-bucket-session-test-isolation'
date: '2026-06-03'
modified: '2026-06-03'
related:
  - '[[2026-06-03-bare-invocation-bucket-session-gate-adr]]'
---



# `cli-bucket-session-test-isolation` audit: `CliRunner ContextVar session non-persistence`

## Scope

Full-suite probe `bmt3ncd38` (323 reds, 2026-06-03) surfaced ~30+ CLI tests failing with one shared error:

`INTEGRITY_STORAGE_VALIDATION: No active bucket session is open. Run aeat config profile switch NAME to unlock a profile.`

Affected clusters: `test_modelo_discovery_defects` (14 reds), `test_modelo_period_consistency` (6 reds), `test_cli_workflow_verification` (15 reds, partial overlap), and subsets of `test_cli_surface` (13 reds, partial). Cluster discovered while attempting mechanical remediation in Phase P10 → P15/P16 of the suite-redgreen plan.

## Findings

### F1 critical — CliRunner ContextVar session is per-invocation

The active bucket session is held in a `ContextVar` on the encrypted-column path. Test code uses `invoke_cached_cli` from `src/aeat/tests/cli_runner.py`, which calls `CliRunner.invoke(...)` once per logical CLI command. Each `invoke()` enters the root callback `_root` then `_activate_active_bucket_session`, which opens the session via `ctx.with_resource(get_master_key_provider())`. When `invoke()` returns, the typer `Context` exits and the ContextVar resets to `None`. The session does NOT survive across two consecutive `invoke_cached_cli` calls.

Production CLI does not hit this path: a real `aeat` invocation is one process per command, the session opens, the verb body runs, the process exits. `invoke_cached_cli` collapses many production-process invocations into one Python process, breaking session continuity that production-shape invocations would never have needed.

### F2 — `profile switch` does write the active-bucket pointer but the session itself never escapes the invoke that wrote it

`profile switch` invokes `_activate_profile_override` which writes the active-bucket pointer file on disk AND calls `ctx.with_resource(override_settings(aeat_active_profile=pointer.bucket_id))`. The disk pointer survives; the ContextVar override does not. So a subsequent `invoke_cached_cli(["app", "modelo", "work", "create", ...])` reads the pointer correctly via `resolve_active_bucket_id()` (so the `if resolve_active_bucket_id() is None: return` guard at the root callback line 272 passes), then SHOULD open the session via `ctx.with_resource(get_master_key_provider())` at line 286, but the actual encrypted-column read fires inside the verb body and the ContextVar at that depth is `None`.

Hypothesis to verify (deferred to coder): the master-key provider opens a session whose ContextVar token only binds within the `_activate_active_bucket_session` frame. If the verb body opens a new dispatch frame (subcommand dispatch via typer), the ContextVar inherited from the parent SHOULD propagate per PEP 567 — but if the per-invocation typer Context is the context the ContextVar is bound to, the binding evaporates as soon as the invocation's outermost frame returns.

### F3 — production path is correct; the bug is fixture-shape

Real operators invoke each CLI command in a fresh process. Process boundary == ContextVar reset. So the production sequence `profile switch operator && aeat app modelo work create ...` works correctly. The test shape (single Python process, two `invoke_cached_cli` calls) is the failure mode.

## Recommendations

### R1 — author shared test helper that wraps the encrypted-store invocation in a real `activate_session` block

The test should not rely on `invoke_cached_cli` to open the session. After `profile switch operator`, the test infrastructure should explicitly enter `activate_session(BucketSession.for_active_profile(...))` and then call `invoke_cached_cli` for the subsequent commands within that block. Existing helper `activate_session` at `src/aeat/adapters/persistence/storage/master_key/_active_session.py:60` already provides the contextmanager.

Proposed helper: `src/aeat/tests/cli_runner.py::with_active_bucket_session(profile_name: str)` context manager that resolves the active bucket pointer, creates a BucketSession, enters `activate_session`, and yields. Each affected test wraps the multi-invocation block in `with with_active_bucket_session("operator"):`.

### R2 — alternative: extend `invoke_cached_cli` with a `keep_session_open` mode

`keep_session_open=True` would have the helper itself enter `activate_session` once, then run the click command inside that block. Less explicit than R1 but requires fewer test-site edits.

### R3 — short-term: dispatch coder to write helper R1 and rewrite the 3-4 affected test files to use it

Estimated scope: helper authoring + ~30-line edit across `test_modelo_discovery_defects.py`, `test_modelo_period_consistency.py`, `test_cli_workflow_verification.py`, plus selected sections of `test_cli_surface.py`. Clears ~30+ suite reds in one atomic landing.

### R4 — ADR amendment to the bare-invocation-bucket-session-gate ADR

The bare-invocation ADR widened the gate; it did not update the test-runner contract. The amended ADR (or a sibling) should document the per-process semantics and the test-helper requirement.

## Codification candidates

- **Source:** finding F3 (per-process session boundary).
  **Rule slug:** `cli-test-bucket-session-must-be-explicit`.
  **Rule:** Test code invoking CLI commands that touch encrypted storage MUST open the bucket session explicitly via the shared test helper; relying on `invoke_cached_cli` to inherit a session opened in a sibling `invoke_cached_cli` is forbidden (the ContextVar resets at invocation boundary, but the disk pointer persists — readers should not conflate the two).


