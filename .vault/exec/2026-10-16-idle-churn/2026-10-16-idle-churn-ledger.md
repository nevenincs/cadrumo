---
tags:
  - '#exec'
  - '#idle-churn'
date: '2026-10-16'
modified: '2026-10-16'
body_schema: 'body-v2'
body_hash: 'sha256:252707ea76aab70dc69ef9dc84284ba80195c68bac769f574a2e41cb04093608'
related:
  - "[[2026-10-16-idle-churn-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `idle-churn` ledger

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

- `S01` `M` `src/cadrumo_client/contracts/service_access.py`
- `S01` `M` `src/cadrumo/core/path_confinement.py`
- `S01` `M` `src/cadrumo_runtime/adapters/service_verification.py`
- `S01` `M` `src/cadrumo_runtime/host/profile_connection_extension_records.py`
- `S01` `M` `src/cadrumo_runtime/host/profile_connection_services.py`
- `S01` `M` `src/cadrumo_runtime/host/tests/test_service_records.py`
- `S01` `A` `src/cadrumo_runtime/adapters/tests/test_service_verification.py`
- `S01` `verify:` `pytest -n0 -m '' test_service_verification.py test_service_records.py` -> `pass`
- `S01` `verify:` `ruff check + ruff format --check + ty check on touched files` -> `pass`
- `S02` `M` `src/cadrumo_runtime/host/worker_service.py`
- `S02` `M` `src/cadrumo_runtime/host/worker_operation_requests.py`
- `S02` `M` `src/cadrumo/adapters/persistence/storage/master_key/profile_worker_custody.py`
- `S02` `M` `src/cadrumo_runtime/host/profile_login.py`
- `S02` `M` `src/cadrumo_runtime/host/worker_submission_staging.py`
- `S02` `M` `src/cadrumo_runtime/host/tests/test_worker_exit_cleanup.py`
- `S02` `M` `src/cadrumo_runtime/host/tests/test_worker_submission_staging.py`
- `S02` `M` `src/cadrumo_runtime/host/tests/test_human_login_receipt.py`
- `S02` `M` `src/cadrumo/adapters/persistence/storage/master_key/tests/test_profile_worker_custody_lease_window.py`
- `S02` `verify:` `pytest -n0 worker exit cleanup, submission staging, custody lease window` -> `pass`
- `S02` `verify:` `pytest -n0 test_human_login_receipt.py` -> `fail`
- `S02` `verify:` `ruff check, ruff format --check, ty check on touched files` -> `pass`
- `S03` `M` `src/cadrumo_client/contracts/session_events.py`
- `S03` `M` `src/cadrumo_client/contracts/sign_in.py`
- `S03` `M` `src/cadrumo_client/transport/verified_transport.py`
- `S03` `M` `src/cadrumo_client/transport/frontend_client.py`
- `S03` `M` `src/cadrumo_runtime/host/session_events.py`
- `S03` `M` `src/cadrumo_runtime/host/profile_connections.py`
- `S03` `M` `src/cadrumo_runtime/host/profile_connection_sessions.py`
- `S03` `M` `src/cadrumo_runtime/host/profile_connection_services.py`
- `S03` `M` `src/cadrumo_runtime/host/profile_connection_attendance.py`
- `S03` `M` `src/cadrumo_runtime/host/profile_connection_operations.py`
- `S03` `M` `src/cadrumo_runtime/host/tests/test_profile_language_events.py`
- `S03` `A` `src/cadrumo_runtime/host/tests/test_connection_cues.py`
- `S03` `A` `src/cadrumo_runtime/host/tests/test_sign_in_watch.py`
- `S03` `A` `src/cadrumo_client/transport/tests/test_invalidation_cues.py`
- `S03` `verify:` `pytest -n0 connection cues, sign-in watch, attendance, lifecycle notices, session events, sign-in status, service records, client cue and language tests` -> `pass`
- `S03` `verify:` `ruff check, ruff format --check, ty check on touched files` -> `pass`
- `S04` `M` `src/cadrumo_agent_service/main.py`
- `S04` `M` `src/cadrumo_agent_service/service.py`
- `S04` `M` `src/cadrumo_agent_service/providers/persistence/store.py`
- `S04` `M` `src/cadrumo_client/transport/service_client.py`
- `S04` `M` `src/cadrumo_agent_service/host/tests/test_service_stdin_lifetime.py`
- `S04` `A` `src/cadrumo_agent_service/providers/persistence/tests/test_store_generations.py`
- `S04` `verify:` `pytest -n0 service stdin lifetime, store generations, hosted certification, admin authority` -> `pass`
- `S04` `verify:` `ruff check, ruff format --check, ty check on touched files` -> `pass`
- `S05` `M` `src/cadrumo_runtime/host/session_hold.py`
- `S05` `M` `src/cadrumo_runtime/host/tests/test_session_hold_stdin_lifetime.py`
- `S05` `verify:` `pytest -n0 test_session_hold_stdin_lifetime.py test_session_hold_frontend.py` -> `pass`
- `S05` `verify:` `ruff check, ruff format --check, ty check on touched files` -> `pass`
- `S06` `A` `src/cadrumo_runtime/host/session_watch.py`
- `S06` `A` `src/cadrumo_runtime/host/tests/test_session_watch.py`
- `S06` `M` `src/cadrumo_runtime/host/bootstrap.py`
- `S06` `M` `src/cadrumo_runtime/host/arguments.py`
- `S06` `M` `src/cadrumo_client/transport/frontend_client.py`
- `S06` `M` `dev/quality/metadata/import_load_targets.cadrumo_runtime.json`
- `S06` `M` `dev/quality/metadata/import_load_targets.json`
- `S06` `verify:` `pytest -n0 test_session_watch.py test_invalidation_cues.py` -> `pass`
- `S06` `verify:` `ruff check, ruff format --check, ty check on touched files` -> `pass`
- `S07` `A` `native/desktop/src-tauri/src/shell/sign_in/watch.rs`
- `S07` `D` `native/desktop/src-tauri/src/shell/sign_in/reads.rs`
- `S07` `M` `native/desktop/src-tauri/src/shell/sign_in/mod.rs`
- `S07` `M` `native/desktop/src-tauri/src/shell/sign_in/observation.rs`
- `S07` `M` `native/desktop/src-tauri/src/shell/sign_in/wire.rs`
- `S07` `M` `native/desktop/src-tauri/src/shell/sign_in/wire_contract_tests.rs`
- `S07` `M` `native/desktop/src-tauri/src/shell/agent_access/wire.rs`
- `S07` `M` `native/desktop/src-tauri/src/shell/provider_settings/wire.rs`
- `S07` `M` `native/desktop/src-tauri/src/shell/language.rs`
- `S07` `M` `native/desktop/src-tauri/src/agent/person.rs`
- `S07` `M` `native/desktop/src-tauri/src/agent/mod.rs`
- `S07` `M` `native/desktop/src-tauri/src/agent/supervisor.rs`
- `S07` `M` `native/desktop/frontend/src/components/AttendanceRequests.tsx`
- `S07` `M` `native/desktop/frontend/src/shell/host.ts`
- `S07` `M` `native/desktop/frontend/src/shell/tauriHost.ts`
- `S07` `M` `native/desktop/frontend/src/ipc/contract.ts`
- `S07` `M` `src/cadrumo_runtime/host/session_watch.py`
- `S07` `M` `src/cadrumo_runtime/host/tests/test_session_watch.py`
- `S07` `verify:` `cmake --build build/windows-x64 --target desktop-host-unit-clippy` -> `pass`
- `S07` `verify:` `cmake --build build/windows-x64 --target desktop-host-unit-test` -> `pass`
- `S07` `verify:` `pnpm tsc eslint prettier` -> `pass`
- `S07` `verify:` `pytest src/cadrumo_runtime/host/tests/test_session_watch.py` -> `pass`
- `S08` `A` `src/cadrumo_client/transport/native_wake.py`
- `S08` `M` `src/cadrumo_client/contracts/contracts.py`
- `S08` `M` `src/cadrumo_client/transport/windows_channel.py`
- `S08` `M` `src/cadrumo_client/transport/posix_channel.py`
- `S08` `M` `src/cadrumo_client/transport/verified_transport.py`
- `S08` `M` `src/cadrumo_runtime/host/session_events.py`
- `S08` `M` `src/cadrumo_runtime/contracts/profile_host.py`
- `S08` `M` `src/cadrumo_runtime/host/profile_connections.py`
- `S08` `M` `src/cadrumo_runtime/adapters/server_connection_handling.py`
- `S08` `M` `src/cadrumo_runtime/adapters/server.py`
- `S08` `M` `src/cadrumo_runtime/host/worker_operation_requests.py`
- `S08` `M` `src/cadrumo_runtime/adapters/worker_authorization.py`
- `S08` `M` `src/cadrumo/entrypoints/cli/tests/test_operation_registered_operation.py`
- `S08` `M` `src/cadrumo_client/transport/tests/test_launch_door_cleanup.py`
- `S08` `M` `src/cadrumo_client/transport/tests/test_runtime_client.py`
- `S08` `M` `src/cadrumo_runtime/adapters/tests/test_access_management_framing.py`
- `S08` `M` `src/cadrumo_runtime/adapters/tests/test_connection_serialization.py`
- `S08` `M` `src/cadrumo_runtime/adapters/tests/test_enrollment_framing.py`
- `S08` `M` `src/cadrumo_runtime/adapters/tests/test_framing.py`
- `S08` `M` `src/cadrumo_runtime/adapters/tests/test_frontend_access_management.py`
- `S08` `M` `src/cadrumo_runtime/adapters/tests/test_launch_door.py`
- `S08` `M` `src/cadrumo_runtime/adapters/tests/test_profile_worker_cleanup.py`
- `S08` `M` `src/cadrumo_runtime/adapters/tests/test_projection_page_client.py`
- `S08` `M` `src/cadrumo_runtime/adapters/tests/test_server_cleanup.py`
- `S08` `M` `src/cadrumo_runtime/adapters/tests/test_worker_lease_transfer.py`
- `S08` `M` `src/cadrumo_runtime/host/tests/frontend/cli/portable_human_cli_runtime.py`
- `S08` `M` `src/cadrumo_runtime/host/tests/operation_transport_support.py`
- `S08` `M` `src/cadrumo_runtime/host/tests/test_installation_door.py`
- `S08` `M` `src/cadrumo_runtime/host/tests/test_worker_construction_cleanup.py`
- `S08` `M` `src/cadrumo_runtime/host/tests/test_worker_exit_cleanup.py`
- `S08` `A` `src/cadrumo_client/transport/tests/test_channel_readiness_wait.py`
- `S08` `A` `src/cadrumo_runtime/adapters/tests/test_server_idle_wait.py`
- `S08` `A` `src/cadrumo_runtime/host/tests/test_worker_request_wait.py`
- `S08` `M` `src/cadrumo_runtime/host/tests/test_session_events.py`
- `S08` `verify:` `pytest src/cadrumo_client/transport/tests src/cadrumo_runtime/adapters/tests` -> `fail`
- `S08` `verify:` `pytest serial runtime host server-backed files` -> `fail`
- `S08` `verify:` `pytest test_channel_readiness_wait test_server_idle_wait test_worker_request_wait test_session_events` -> `pass`
- `S08` `verify:` `ruff ty basedpyright pyrefly lint-imports on touched files` -> `pass`

## Notes

- `S01` `profile_connection_services.py` interleaves with another session's uncommitted lease-guard and refusal-check hunks; its claim and admission recheck stays uncommitted until those land, while HEAD's full verification there still works with the new verifier.
- `S02` `test_worker_human_login_receipt_lifecycle[success]` fails on CADRUMO-RUNTIME-DEBUG's uncommitted `_ended` change in `profile_worker_custody.retire` (retired sessions now refuse with `authentication_required);` the other seven modes pass and the failure was reported to that session.
- `S03` Four files carry other sessions' uncommitted hunks; this Step's edits were staged as a HEAD-relative patch with git apply --cached, leaving theirs in the working tree. The S01 claim and admission recheck rides in the same patch.
- `S04` AgentDiagnosticFiles still tails the hosted agent's log files every 0.2 s while an agent runs; directory change notifications fire only when a writer closes its handle (measured: at exit), so moving it to them needs a decision on worker diagnostics with the cadrumo-agent owner.
- `S05` `session_hold.py` carries another session's `_report_failure` and `OS_SESSION_UNAVAILABLE` hunks; this Step was staged as a HEAD-relative patch. Pushed lines are opt-in through `observe_events,` so a desktop built before S07 keeps its strict request-reply bridge.
- `S06` End-to-end use against the packaged runtime is verified with the desktop in S10; the runtime cue path itself is covered by `test_sign_in_watch.py` from S03.
- `S07` Commit carries CADRUMO-FIX1's shared-person hunks by agreement; CADRUMO-BUILD-DEBUG's diagnostics and `with_reason` calls stay uncommitted pending its ApplicationError reason API; the committed tree was not compiled separately from the working tree
- `S08` Adapter and transport suites: 913 passed, 1 failed `(test_posix_login_capture,` an unowned uncommitted pidfd option rename in `posix_channel.py).` Host suite: 211 passed, 5 failed, all from other sessions' uncommitted changes: the receipt handover in `profile_connection_sessions.py` and the `AUTHENTICATION_REQUIRED` session mismatch in `profile_connection_operations.py.` The stop-wake gate was shown to fail with the wake removed.
