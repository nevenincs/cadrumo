---
tags:
  - '#exec'
  - '#operation-cues'
date: '2026-10-17'
modified: '2026-10-17'
body_schema: 'body-v2'
body_hash: 'sha256:9a965f80a84bde7ec365f8385082a98e731eb2578cc35ba2ada374a82f5eda2e'
related:
  - "[[2026-10-17-operation-cues-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `operation-cues` ledger

## Changes

<!-- MECHANICAL LOG, append-only, one row per path touched per Step, written
     by `--row`:
       - `S##` `A` `path`   added
       - `S##` `M` `path`   modified
       - `S##` `D` `path`   deleted
       - `S##` `R` `old` -> `new`   renamed
     Paths are repo-relative, in backticks. No prose: the Step row states the
     intent and the commit carries the diff.

     Optional per-Step rows, written by `--verify` and `--by`:
       - `S##` `verify:` `<command>` -> `pass` | `fail`
       - `S##` `by:` `<persona>`

     Rows are appended in Step order and never rewritten. Only rows in this
     section register a Step as covered. `--note` adds a `## Notes` section
     ONLY on exception (data loss, skipped work, a scaffold left in code, a
     persistent failure), one `S##`-prefixed line each; it is otherwise
     omitted. -->

- `S01` `M` `src/cadrumo/adapters/persistence/operations/durability_router.py`
- `S01` `M` `src/cadrumo/adapters/persistence/operations/tests/test_durability_router.py`
- `S01` `M` `src/cadrumo/entrypoints/operation_composition.py`
- `S01` `M` `src/cadrumo_runtime/contracts/worker_authorization.py`
- `S01` `M` `src/cadrumo_runtime/adapters/worker_authorization.py`
- `S01` `M` `src/cadrumo_runtime/adapters/worker_authorization_client.py`
- `S01` `M` `src/cadrumo_runtime/adapters/tests/worker_authorization_fixture.py`
- `S01` `M` `src/cadrumo_runtime/adapters/tests/test_worker_authorization.py`
- `S01` `M` `src/cadrumo_runtime/host/operation_host.py`
- `S01` `M` `src/cadrumo_runtime/host/profile_host.py`
- `S01` `A` `src/cadrumo_runtime/host/operation_progress_reporter.py`
- `S01` `A` `src/cadrumo_runtime/host/tests/test_operation_progress_reporter.py`
- `S01` `verify:` `pytest -m integration test_durability_router.py` -> `pass`
- `S01` `verify:` `pytest test_operation_progress_reporter.py` -> `pass`
- `S01` `verify:` `pytest -m integration test_worker_authorization.py` -> `pass`
- `S01` `verify:` `pytest operation host and persistence suites` -> `pass`
- `S01` `verify:` `ruff check, ruff format --check, ty check, lint-imports` -> `pass`
- `S02` `M` `src/cadrumo_client/contracts/session_events.py`
- `S02` `M` `src/cadrumo_client/transport/frontend_client.py`
- `S02` `M` `src/cadrumo_runtime/host/session_events.py`
- `S02` `M` `src/cadrumo_runtime/host/profile_connection_operations.py`
- `S02` `M` `src/cadrumo_runtime/host/profile_connection_admission.py`
- `S02` `M` `src/cadrumo_runtime/host/profile_connection_sessions.py`
- `S02` `M` `src/cadrumo_runtime/host/profile_connections.py`
- `S02` `M` `src/cadrumo_runtime/host/tests/test_connection_cues.py`
- `S02` `verify:` `pytest test_connection_cues.py` -> `pass`
- `S02` `verify:` `pytest -m unit cadrumo_runtime/host/tests cadrumo_client/transport/tests cadrumo_client/contracts` -> `pass`
- `S02` `verify:` `ruff check, ruff format --check, ty check` -> `pass`
- `S03` `A` `src/cadrumo_client/transport/operation_changes.py`
- `S03` `M` `src/cadrumo_client/transport/operation_settlement.py`
- `S03` `M` `src/cadrumo_client/commands/registered_operation_observations.py`
- `S03` `M` `src/cadrumo_client/commands/registered_operation_deadlines.py`
- `S03` `M` `src/cadrumo_client/transport/tests/test_operation_settlement.py`
- `S03` `M` `src/cadrumo/entrypoints/cli/tests/test_operation_registered_operation.py`
- `S03` `M` `src/cadrumo/entrypoints/cli/tests/test_operation_operation_error_detail.py`
- `S03` `M` `src/cadrumo/entrypoints/cli/tests/test_operation_modelo_filing_settlement.py`
- `S03` `verify:` `pytest -m unit cadrumo_client, entrypoints/cli/tests, cli/config/tests, cadrumo_runtime/host/tests` -> `pass`
- `S03` `verify:` `pytest -m integration test_runtime_modelo_work_create_native.py` -> `pass`
- `S03` `verify:` `ruff check, ruff format --check, ty check, lint-imports` -> `pass`
- `S04` `M` `src/cadrumo/entrypoints/cli/config/operation_censal_observation.py`
- `S04` `M` `src/cadrumo/entrypoints/cli/config/operation_censal_review.py`
- `S04` `M` `src/cadrumo/entrypoints/tui/google_saved_review.py`
- `S04` `M` `src/cadrumo/entrypoints/tui/operations/controller_port.py`
- `S04` `M` `src/cadrumo/entrypoints/tui/operations/modal.py`
- `S04` `M` `src/cadrumo/entrypoints/tui/operations/tests/test_await_terminal_projection.py`
- `S04` `A` `src/cadrumo/entrypoints/tui/operations/tests/test_modal_operation_cues.py`
- `S04` `M` `src/cadrumo/entrypoints/tui/tests/test_google_saved_review.py`
- `S04` `M` `src/cadrumo_client/commands/runtime_google_consent.py`
- `S04` `M` `src/cadrumo_client/transport/frontend_client.py`
- `S04` `M` `src/cadrumo_client/transport/frontend_operation_client.py`
- `S04` `M` `src/cadrumo_client/transport/frontend_profile_view_client.py`
- `S04` `M` `src/cadrumo_client/transport/operation_changes.py`
- `S04` `M` `src/cadrumo_client/transport/operation_controller.py`
- `S04` `M` `src/cadrumo_client/transport/operation_reads.py`
- `S04` `M` `src/cadrumo_client/transport/profile_password_rotation.py`
- `S04` `M` `src/cadrumo_runtime/host/frontend/tui/aeat_sync/runtime_handoff.py`
- `S04` `M` `src/cadrumo_runtime/host/tests/frontend/cli/portable_human_cli_runtime.py`
- `S04` `M` `src/cadrumo_runtime/host/tests/frontend/tui/aeat_sync/test_runtime_handoff.py`
- `S04` `verify:` `pytest -m 'unit or integration' src/cadrumo_client src/cadrumo/entrypoints/cli src/cadrumo/entrypoints/tui src/cadrumo_runtime/host/tests/frontend src/cadrumo_harness/mcp/tests` -> `pass`
- `S05` `M` `src/cadrumo_client/contracts/session_events.py`
- `S05` `M` `src/cadrumo_client/transport/frontend_client.py`
- `S05` `M` `src/cadrumo_harness/mcp/runtime_admission.py`
- `S05` `A` `src/cadrumo_harness/mcp/tests/test_attendance_wait.py`
- `S05` `M` `src/cadrumo_harness/mcp/tests/test_sign_in_resume.py`
- `S05` `M` `src/cadrumo_runtime/host/profile_connection_attendance.py`
- `S05` `M` `src/cadrumo_runtime/host/session_events.py`
- `S05` `M` `src/cadrumo_runtime/host/tests/test_attendance.py`
- `S05` `verify:` `pytest src/cadrumo_harness/mcp/tests/test_attendance_wait.py src/cadrumo_harness/mcp/tests/test_sign_in_resume.py src/cadrumo_runtime/host/tests/test_attendance.py` -> `pass`
- `S08` `M` `native/manager/src/background.rs`
- `S08` `A` `native/manager/src/change_watch.rs`
- `S08` `M` `native/manager/src/cutover_coordinator.rs`
- `S08` `M` `native/manager/src/installation_watch.rs`
- `S08` `M` `native/manager/src/lib.rs`
- `S08` `M` `native/manager/src/lifecycle.rs`
- `S08` `verify:` `ctest --preset debug --tests-regex ^manager\.(rust|supervision)$` -> `pass`
- `S08` `verify:` `cmake --build --preset debug --target check_manager_lifecycle` -> `pass`
- `S08` `M` `native/manager/src/desktop_host.rs`
- `S08` `M` `native/manager/src/session.rs`
- `S08` `M` `native/manager/src/session/instance.rs`
- `S08` `A` `native/manager/src/session/status_cue.rs`
- `S08` `M` `native/manager/src/session/windows.rs`
- `S08` `M` `native/manager/src/windows_lifecycle.rs`
- `S08` `verify:` `ctest --preset debug --tests-regex ^manager\.(rust|supervision)$` -> `pass`
- `S08` `verify:` `cmake --build --preset debug --target check_manager_lifecycle` -> `pass`
- `S08` `verify:` `cmake --build --preset debug --target desktop-host-unit-clippy` -> `pass`
- `S08` `verify:` `cmake --build --preset debug --target desktop-host-unit-test` -> `pass`
- `S01` `M` `src/cadrumo_runtime/host/operation_progress_reporter.py`
- `S01` `M` `src/cadrumo_runtime/host/tests/test_operation_progress_reporter.py`
- `S01` `A` `.vault/audit/2026-10-17-operation-cues-audit.md`
- `S01` `verify:` `pytest -n0 test_operation_progress_reporter.py` -> `pass`
- `S01` `verify:` `escaping-error test against the previous reporter (expected to fail)` -> `fail`
- `S01` `verify:` `ruff check, ruff format --check, ty check on the reporter and its test` -> `pass`
- `S01` `verify:` `dev.quality.types diagnostics in the reporter (none)` -> `pass`
- `S01` `by:` `tui-41 (took over from CADRUMO-BUILD-DEBUG)`

## Notes

- `S02` `test_frontend_boundaries::test_installed_composition_and_native_journeys_are_runtime_owned` fails before and after this Step: it asserts a test file another session deleted
- `S03` Pre-existing, unchanged by this Step: 9 CLI structural/inventory tests, `test_frontend_boundaries` (deleted file), and `test_runtime_ledger_reads_native::test_native_api_ledger_status_requires_all_periods_even_when_query_selects_one,` which fails one run in three even with the reporter disabled and the old client code
- `S04` The wide run's pre-existing failures were fixed separately in d07ae808aa (resolution-cost child import, environment reference conformance); the portable fixture's stale `_lapsed` field is fixed in this Step's commit.
- `S08` Partial: the desktop host's 1 s external-owner pace remains. It mirrors the external manager's status, and the manager IPC has no change signal; removing it needs a status-wait in the manager protocol, pending the user's decision.
- `S01` Plan-close review finding reporter-thread-not-replaced, fixed after S01 closed; the medium finding modal-waits-unbounded-on-a-dropped-report stays open for the operator's decision.
