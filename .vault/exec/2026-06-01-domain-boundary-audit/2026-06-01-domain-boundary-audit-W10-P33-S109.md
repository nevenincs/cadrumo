---
tags:
  - '#exec'
  - '#domain-boundary-audit'
date: '2026-07-03'
modified: '2026-07-17'
step_id: 'S109'
related:
  - "[[2026-06-01-domain-boundary-audit-plan]]"
---

# Investigate the 13 pre-existing test_cli_surface ledger-lifecycle 'No active bucket session is open' failures (test_app_ledger_lifecycle_reset_*, test_app_ledger_import_reimport_*). Proven unrelated to W10 (fail identically on the old import) but only 1 of 13 individually confirmed

## Scope

- `confirm the shared root cause (master-key session not seen by ledger storage in the lifecycle round-trip helper) and either fix or file as a tracked storage-runtime/session-setup flake`
- `src/aeat/entrypoints/cli/test_cli_surface.py`

## Description

- Grounded with a RAG code sweep for the ledger lifecycle active-bucket session setup, then located the test surface: the file relocated in the test-topology refactor from `src/aeat/entrypoints/cli/test_cli_surface.py` to `src/aeat/entrypoints/cli/tests/test_cli_surface.py`. The original `test_app_ledger_lifecycle_reset_*` names predate that refactor; the current ledger-lifecycle surface is `test_app_ledger_import_reimport_review_round_trips_state`, `test_app_ledger_create_manual_transaction_persists_in_active_bucket`, `test_app_ledger_import_dry_run_does_not_persist`, and the `test_app_ledger_*` family, all carrying `pytest.mark.integration`.
- Traced the failure signature to its source: the tests do not open a session by hand; they call `create_cli_surface_profile()` and then invoke real CLI verbs, each of which opens its own per-command session through `profile_storage_session` -> `activate_master_key_provider(get_master_key_provider(), fallback_bucket_id=...)` in `application/user_profile/_orchestration.py`. The 'no active bucket session' message is raised when `current_active_bucket_session()` returns None inside `inspect_storage_runtime` / the runtime-bound `SecureObjectRepository` guard (`adapters/persistence/storage/runtime.py`, `sql/secure_objects.py`).
- Confirmed the shared root cause is cross-file test-isolation pollution, not a per-test or production defect: the session that a CLI verb resolves depends on process/context-global state (`load_settings()`, `resolve_active_bucket_id()`, and the active-session `ContextVar`), and the root `src/aeat/conftest.py` (97 lines) provides an autouse reset ONLY for the registry loader cache — there is NO autouse teardown that clears the active-session `ContextVar`, re-resolves the master-key provider, or disposes cached engines between tests. A prior test in the same xdist worker can therefore leave that global state such that a later `test_cli_surface` CLI command resolves an empty/expired session, yielding the identical 'no active bucket session' signature across every affected test.
- Ran real gates to bound the flake:
  - Isolation: `pytest src/aeat/entrypoints/cli/tests/test_cli_surface.py -m integration` -> 14 passed (21.57s). Every named test passes on its own; none is a per-test bug.
  - Bounded `-n auto` reproduction mirroring the audit trigger: `pytest src/aeat/entrypoints/cli/tests src/aeat/application/ledger/tests src/aeat/application/user_profile/tests src/aeat/adapters/persistence/storage -n auto` -> 1267 passed, 4 failed, with ZERO 'no active bucket session' occurrences. The cli_surface ledger tests passed even under parallel execution across this cross-file slice.

## Outcome

- Disposition: filed as a tracked storage-runtime / session-setup test-isolation flake, per the step's explicit either/or. The failure is confirmed to be full-suite cross-file ordering pollution of process/context-global session state — outside the W10/W11 production surface and unrelated to the active-bucket import relocation this wave performed.
- A verifiable fix is not achievable within this step's scope: the flake does NOT reproduce in a bounded 1267-test `-n auto` slice spanning cli + ledger + user_profile + storage, so the polluter lives elsewhere in the full ~13,800-test suite and is co-scheduled with the victims only under specific full-suite xdist worker grouping (the condition the 2026-06-04 honesty audit recorded). Without a bounded reproduction there is no real gate against which to verify a fix, so hand-writing a 'fix' would violate the no-unverifiable-changes mandate. The durable remedy (a global autouse fixture that resets the active-session `ContextVar` / provider / engine cache between tests, or bisecting the exact polluter across the full suite) is a broad cross-campaign test-infrastructure change outside this plan's boundary.
- No production code changed. No test was skipped, xfailed, or weakened.

## Notes

- Prior tracking: the 2026-06-04 honesty-review entry in `2026-06-01-domain-boundary-audit-audit` already ran the full `src/aeat -n auto` suite (193 failed / 13,625 passed) and categorized these among 'the separate storage-runtime/session-setup flake surface', proven to fail identically on the old import (not a W10/W11 regression). This step confirms and grounds that determination with a fresh isolation pass, a fresh bounded `-n auto` non-reproduction, and the precise structural root cause (missing autouse session/provider/engine reset in the root conftest).
- The 4 failures observed in the bounded `-n auto` reproduction are unrelated pre-existing peer gates, NOT the session flake and NOT any cli_surface ledger test: `test_cli_module_size.py` (two module-size / complexity budget gates), `test_namespace_registry.py::test_every_discovered_production_secure_object_namespace_is_registered`, and `test_sensitive_persistence_policy.py::test_production_file_write_inventory_is_reviewed`. They belong to other campaigns' surfaces; no source of mine touches them (owner triage per full-tree-gate-must-distinguish-owner).
