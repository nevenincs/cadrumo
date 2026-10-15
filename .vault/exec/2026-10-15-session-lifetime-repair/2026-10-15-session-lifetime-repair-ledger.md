---
tags:
  - '#exec'
  - '#session-lifetime-repair'
date: '2026-10-15'
modified: '2026-10-15'
body_schema: 'body-v2'
body_hash: 'sha256:8c0afe97d2b9f5302318ca13904a77793ed57d149cbee0d95aadf5a8e86061c8'
related:
  - "[[2026-10-15-session-lifetime-repair-plan]]"
---

# `session-lifetime-repair` ledger

## Changes

- `S02` `M` `native/desktop/src-tauri/src/app.rs`
- `S02` `M` `native/desktop/src-tauri/src/terminal/mod.rs`
- `S02` `M` `native/desktop/src-tauri/src/terminal/tests.rs`
- `S02` `M` `native/application/src/diagnostics/mod.rs`
- `S02` `M` `native/desktop/src-tauri/src/logs/severity.rs`
- `S02` `verify:` `configured native backend full unit suite (329 tests)` -> `pass`
- `S02` `verify:` `configured native backend Clippy` -> `pass`
- `S02` `verify:` `packaged Debug and Release stdin-open shutdown probes` -> `pass`
- `S01` `A` `src/cadrumo_runtime/application/session_authority_activity.py`
- `S01` `M` `src/cadrumo_runtime/application/session_authority.py`
- `S01` `M` `src/cadrumo_runtime/application/session_authority_core.py`
- `S01` `M` `src/cadrumo_runtime/application/tests/test_session_authority.py`
- `S01` `M` `src/cadrumo_runtime/host/profile_connection_sessions.py`
- `S01` `M` `src/cadrumo_runtime/host/profile_login.py`
- `S01` `M` `src/cadrumo_runtime/host/worker_service.py`
- `S01` `M` `src/cadrumo_runtime/host/session_hold.py`
- `S01` `M` `src/cadrumo_runtime/host/tests/test_human_login_receipt.py`
- `S01` `M` `src/cadrumo_runtime/host/tests/test_profile_connections.py`
- `S01` `M` `src/cadrumo_runtime/host/tests/test_person_act_frontend_matrix.py`
- `S01` `M` `src/cadrumo_client/contracts/profile_access.py`
- `S01` `M` `src/cadrumo_client/contracts/session_policy.py`
- `S01` `M` `src/cadrumo_client/transport/frontend_client.py`
- `S01` `M` `src/cadrumo/adapters/persistence/storage/custody/acceleration_receipt.py`
- `S01` `M` `src/cadrumo/adapters/persistence/storage/master_key/profile_worker_custody.py`
- `S01` `M` `src/cadrumo/adapters/persistence/storage/master_key/tests/test_profile_worker_custody_lease_window.py`
- `S01` `M` `src/cadrumo/adapters/persistence/storage/profile_login_session.py`
- `S01` `M` `src/cadrumo/application/user_profile/login_session.py`
- `S01` `M` `src/cadrumo/application/user_profile/login_session_port.py`
- `S01` `A` `src/cadrumo_runtime/commands/activity.py`
- `S01` `M` `src/cadrumo_runtime/commands/custody_specs.py`
- `S01` `M` `src/cadrumo_client/commands/custody_payloads.py`
- `S01` `A` `src/cadrumo_runtime/commands/tests/config/test_activity.py`
- `S01` `M` `src/cadrumo/locales/en/cli.yml`
- `S01` `M` `src/cadrumo/locales/es/cli.yml`
- `S01` `M` `src/cadrumo/locales/ca/cli.yml`
- `S01` `M` `src/cadrumo/locales/hu/cli.yml`
- `S01` `verify:` `session authority integration file 73 tests` -> `pass`
- `S01` `verify:` `person-act frontend matrix 7 tests and service activity regression` -> `pass`
- `S01` `verify:` `Windows IPC unknown-observation recovery regression` -> `pass`
- `S01` `verify:` `worker receipt integration 14 and adapter4 tests` -> `pass`
- `S01` `verify:` `receipt roundtrip/binding 60 tests` -> `pass`
- `S01` `verify:` `CLI activity and status 9 tests` -> `pass`
- `S01` `verify:` `focused Ruff and ty` -> `pass`
- `S03` `M` `src/cadrumo/core/errors/registry/_entrypoints.py`
- `S03` `M` `src/cadrumo/entrypoints/tui/account.py`
- `S03` `M` `src/cadrumo/entrypoints/tui/app.py`
- `S03` `M` `src/cadrumo/entrypoints/tui/app_navigation.py`
- `S03` `M` `src/cadrumo/entrypoints/tui/installed_session.py`
- `S03` `M` `src/cadrumo/entrypoints/tui/runtime_admission.py`
- `S03` `M` `src/cadrumo/entrypoints/tui/runtime_account_session.py`
- `S03` `M` `src/cadrumo/entrypoints/tui/runtime_initial_root.py`
- `S03` `M` `src/cadrumo/entrypoints/tui/runtime_workbench.py`
- `S03` `M` `src/cadrumo/entrypoints/tui/secret/runtime_login.py`
- `S03` `M` `src/cadrumo/entrypoints/tui/tests/test_app.py`
- `S03` `M` `src/cadrumo/entrypoints/tui/tests/test_installed_session.py`
- `S03` `M` `src/cadrumo/entrypoints/tui/tests/test_runtime_root_shell.py`
- `S03` `M` `src/cadrumo/entrypoints/tui/tests/test_runtime_account_session.py`
- `S03` `M` `src/cadrumo/entrypoints/tui/secret/tests/test_runtime_login.py`
- `S03` `M` `native/desktop/src-tauri/src/shell/sign_in/mod.rs`
- `S03` `M` `native/desktop/src-tauri/src/shell/sign_in/wire.rs`
- `S03` `M` `native/desktop/src-tauri/src/shell/sign_in/wire_contract_tests.rs`
- `S03` `M` `native/desktop/src-tauri/src/shell/sign_in/process.rs`
- `S03` `M` `native/desktop/frontend/src/App.tsx`
- `S03` `M` `native/desktop/frontend/src/ipc/contract.ts`
- `S03` `M` `native/desktop/frontend/src/shell/host.ts`
- `S03` `M` `native/desktop/frontend/src/shell/tauriHost.ts`
- `S03` `M` `native/desktop/frontend/src/dev/scenarioHost.ts`
- `S03` `A` `native/desktop/frontend/src/shell/usePersonActivity.ts`
- `S03` `A` `native/desktop/frontend/tests/scenarios/person-activity.spec.ts`
- `S03` `verify:` `focused TUI session/recovery/admission tests` -> `pass`
- `S03` `verify:` `native shell sign-in 58 tests` -> `pass`
- `S03` `verify:` `native Clippy` -> `pass`
- `S03` `verify:` `frontend TypeScript ESLint and activity Playwright` -> `pass`
- `S01` `M` `src/cadrumo_runtime/host/profile_connections.py`
- `S01` `M` `src/cadrumo_runtime/host/tests/test_one_signed_in_profile.py`
- `S01` `M` `src/cadrumo_client/transport/tests/test_login_scope_frame.py`
- `S01` `M` `dev/quality/metadata/import_load_targets.json`
- `S01` `M` `dev/quality/metadata/import_load_targets.cadrumo_runtime.json`
- `S01` `verify:` `profile handover Windows integration 4 tests` -> `pass`
- `S01` `verify:` `activity intent frame and CLI 19 tests` -> `pass`
- `S01` `verify:` `4770 first-party modules isolated import loadability` -> `pass`
- `S01` `verify:` `final just check-format` -> `pass`

## Notes

- `S02` The existing raw-os.read fix predates this repair. Latest Debug shutdown initiator remains unproven; earlier Release buffered-input crash proven from minidumps. Changes remain uncommitted in a shared dirty worktree.
- `S01` Shared worktree changes are uncommitted; package/global checks belong to S04.
- `S03` Cross-origin documentation iframe input is not captured as person activity. Shared changes uncommitted.
- `S01` Activity-only resumption has no profile-switch side effects; ordinary handover completion and revocation are serialized.
