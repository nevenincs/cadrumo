---
tags:
  - '#exec'
  - '#client-concurrency'
date: '2026-10-26'
modified: '2026-10-26'
body_schema: 'body-v2'
body_hash: 'sha256:69015de59dadb0d3b68115de97cf63dc8a5d2d873a4782fb06b5dabeb056ecc6'
related:
  - "[[2026-10-26-client-concurrency-plan]]"
---

# `client-concurrency` ledger

## Changes

- `S01` `M` `src/cadrumo_client/transport/operation_changes.py`
- `S01` `M` `src/cadrumo_client/transport/operation_controller.py`
- `S01` `A` `src/cadrumo_client/transport/tests/test_operation_changes.py`
- `S01` `M` `src/cadrumo_client/transport/tests/test_operation_controller_binding.py`
- `S01` `M` `src/cadrumo_client/transport/tests/test_channel_readiness_wait.py`
- `S01` `verify:` `uv run --no-sync pytest src/cadrumo_client/transport/tests -q` -> `pass`
- `S01` `verify:` `uv run --no-sync pytest src/cadrumo_client/transport/tests/test_operation_changes.py src/cadrumo_client/transport/tests/test_operation_controller_binding.py -q` -> `pass`
- `S01` `verify:` `uv run --no-sync pytest src/cadrumo_client/transport/tests/test_operation_changes.py src/cadrumo_client/transport/tests/test_channel_readiness_wait.py -m '' -q` -> `pass`
- `S01` `verify:` `just check-types --count` -> `pass`
- `S02` `M` `native/application/src/runtime_client.rs`
- `S02` `verify:` `ctest --test-dir build/windows-x64 -C Debug --output-on-failure -R ^(application.rust|platform.rust)$` -> `pass`
- `S02` `verify:` `ctest --test-dir build/windows-x64 -C Debug --output-on-failure -R ^application.(rustfmt|fmt|clippy|features.clippy)$` -> `pass`
- `S03` `M` `src/cadrumo_client/transport/automation_requester.py`
- `S03` `M` `src/cadrumo_client/transport/profile_password_rotation.py`
- `S03` `M` `src/cadrumo_client/transport/frontend_client.py`
- `S03` `M` `src/cadrumo_client/transport/tests/test_automation_requester.py`
- `S03` `M` `src/cadrumo_client/transport/tests/test_profile_password_rotation.py`
- `S03` `M` `src/cadrumo_client/transport/tests/test_invalidation_cues.py`
- `S03` `verify:` `requester and rotation tests: 26 passed` -> `pass`
- `S03` `verify:` `invalidation tests: 6 passed` -> `pass`
- `S03` `verify:` `TUI modal operation cue tests: 4 passed` -> `pass`
- `S03` `verify:` `focused Ruff and ty` -> `pass`
- `S02` `M` `native/platform/src/runtime_pipe.rs`
- `S03` `M` `src/cadrumo_client/transport/verified_transport.py`
- `S03` `M` `src/cadrumo_client/transport/tests/test_channel_readiness_wait.py`
- `S03` `M` `src/cadrumo_runtime/commands/passphrase.py`
- `S03` `M` `src/cadrumo_runtime/commands/tests/config/test_passphrase_runtime_change.py`
- `S03` `M` `src/cadrumo_runtime/host/frontend/cli/profile_client.py`
- `S03` `M` `src/cadrumo_runtime/host/frontend/tui/installed_session.py`
- `S03` `M` `src/cadrumo_runtime/host/frontend/tui/runtime_access_management.py`
- `S03` `M` `src/cadrumo_runtime/host/frontend/tui/runtime_account.py`
- `S03` `M` `src/cadrumo_runtime/host/tests/frontend/tui/test_runtime_account_factories.py`
- `S03` `M` `src/cadrumo_runtime/host/tests/test_runtime_password_rotation.py`
- `S03` `verify:` `final focused Python selection: 47 tests` -> `pass`
- `S03` `M` `dev/acceptance/review/installed_google_review_tui.py`
- `S03` `M` `dev/runtime_lifecycle/tests/test_mcp_frontend_session_lock_parity.py`
- `S03` `M` `dev/runtime_lifecycle/tests/test_runtime_automation_grant_lock_parity.py`
- `S03` `M` `dev/runtime_lifecycle/tests/test_runtime_automation_management_parity.py`
- `S03` `M` `dev/tui/harness/sequences.py`
- `S03` `M` `src/cadrumo_runtime/host/tests/frontend/tui/entrypoints/tui/declarations/tests/test_declarations_installed_create.py`
- `S03` `M` `src/cadrumo_runtime/host/tests/frontend/tui/entrypoints/tui/tests/test_runtime_workbench_native.py`
- `S03` `M` `src/cadrumo_runtime/host/tests/frontend/tui/profile/test_automation_inventory.py`
- `S03` `M` `src/cadrumo_runtime/host/tests/frontend/tui/test_runtime_access_management.py`
- `S03` `M` `src/cadrumo_runtime/host/tests/frontend/tui/test_runtime_initial_root.py`
- `S03` `M` `src/cadrumo_runtime/host/tests/frontend/tui/test_runtime_language_captures.py`
- `S03` `verify:` `ty and Ruff on 12 recovery consumer files` -> `pass`
- `S03` `verify:` `account factory tests after final signatures: 7 passed` -> `pass`
- `S04` `M` `native/application/src/provisioning/engine.rs`
- `S04` `M` `dev/quality/tests/test_no_model_definitions.py`
- `S04` `verify:` `application.rust application.fmt application.clippy after quick-status hardware fix` -> `pass`
- `S04` `verify:` `model-definition gate 56 tests and scoped ty/Ruff` -> `pass`
- `S04` `M` `src/cadrumo_client/transport/installed_client.py`
- `S04` `M` `src/cadrumo_client/transport/tests/test_runtime_client.py`
- `S04` `verify:` `installed opener ownership and metadata cancellation/deadline tests: 17 passed` -> `pass`
- `S04` `verify:` `installed opener Ruff and ty` -> `pass`

## Notes

- `S01` Concurrent runtime session supplied `verified_transport` disconnect-finally fix and overlapping native-channel tests; combined behavior passed. Benchmark scratch lives in .tmp/client-concurrency: 30000 cues, callbacks 30000 to 30, median burst 13.566 ms to 0.229 ms.
- `S02` Integrated concurrent runtime session's connection-queue, subscription and idle-read changes; principal tightened transfer and already-buffered reply deadlines. Native live runtime acceptance remains separately configured.
- `S02` Include the native idle-read dependency and preserve the handshake deadline across header and payload.
- `S03` Fresh connection attempts receive the remaining rotation budget through CLI and TUI; late admission is refused and closed. Read-only Luna opener review passed.
- `S03` Whole-project ty now reports two diagnostics in concurrent `dev/quality/tests/test_no_model_definitions.py` only. Provisioning timing assertion fails isolated (4.693s); integrated review remains open.
- `S04` Quick status no longer launches hardware queries; full checks/setup retain measurement. First live auth run had one rotation deadline failure; unchanged instrumented rerun passed in29s; canonical rerun and packaged matrix pending.
- `S04` Moved immutable installation/authority metadata reads off the event loop and into the same opening deadline before acquiring native endpoints.
