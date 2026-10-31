---
tags:
  - '#exec'
  - '#macos-platform'
date: '2026-10-30'
modified: '2026-10-31'
body_schema: 'body-v2'
body_hash: 'sha256:fcaa552b04c8421f3c8039382e7b2f2037616ed2d3d4211c80c2c7f625681ac5'
related:
  - "[[2026-10-30-macos-platform-plan]]"
---

# `macos-platform` ledger

## Changes

- `S02` `M` `native/manager/src/custody/posix.rs`
- `S02` `M` `native/manager/src/main.rs`
- `S02` `M` `native/manager/src/macos/lifecycle/appkit.rs`
- `S02` `A` `native/manager/src/macos/menu/effects.rs`
- `S02` `M` `native/manager/src/lib.rs`
- `S02` `M` `native/platform/src/conformance_tests.rs`
- `S02` `M` `native/cmake/RustQuality.cmake`
- `S02` `M` `native/CMakeLists.txt`
- `S02` `M` `native/application/CMakeLists.txt`
- `S02` `M` `dev/packaging/native/cargo_command.py`
- `S02` `M` `dev/packaging/native/build_fingerprint.py`
- `S02` `verify:` `.tmp/2026-10-30-macos-platform/native/build.sh Debug all` -> `pass`
- `S02` `verify:` `ctest --test-dir build/macos-arm64 -C Debug -R ^manager\.` -> `pass`
- `S02` `by:` `vaultspec-high-executor`
- `S03` `M` `src/cadrumo_runtime/adapters/macos_coalition.py
src/cadrumo_runtime/host/tests/test_worker_exit_cleanup.py
src/cadrumo_runtime/host/worker_service.py
src/cadrumo/adapters/outbound/aeat/browser/tests/test_view_input.py
src/cadrumo/adapters/outbound/aeat/browser/view_input.py
src/cadrumo/adapters/persistence/storage/custody/tests/test_kdf_worker_startup_ownership.py
src/cadrumo/application/user_profile/tests/test_language_resolver_snapshot.py
src/cadrumo/core/observability/tests/test_sink.py
src/cadrumo/core/tests/test_bucket_pointer_io.py
src/cadrumo/core/tests/test_output_dir_state_root.py`
- `S03` `verify:` `uv run --no-sync pytest -n 2 rerun of baseline failing files` -> `pass`
- `S03` `M` `dev/packaging/native/platforms/posix.py`
- `S03` `M` `src/cadrumo/core/tests`
- `S03` `M` `src/cadrumo_runtime/adapters/macos_coalition.py`
- `S03` `M` `src/cadrumo/adapters/persistence/storage/custody/tests`
- `S03` `M` `src/cadrumo/application/actividad_asset/disposal_calculation.py`
- `S03` `M` `src/cadrumo/application/modelo/tests/test_filed_register_pass_loads.py`
- `S03` `verify:` `uv run --no-sync pytest --co -q` -> `pass`
- `S03` `verify:` `rerun of 107 baseline failing files: 15 failures, all fixed` -> `pass`
- `S03` `by:` `vaultspec-standard-executor`
- `S05` `M` `dev/packaging/native/product.py`
- `S05` `M` `native/desktop/scripts/frontend-install.mjs`
- `S05` `M` `dev/packaging/native/platforms/posix.py`
- `S05` `verify:` `build/macos-arm64/stage/Debug/app/bin/aeat --version` -> `pass`
- `S05` `verify:` `stage/Debug/app/cadrumo-manager --version` -> `pass`
- `S05` `by:` `vaultspec-high-executor`
- `S06` `A` `native/desktop/macos/bundle_launcher.c`
- `S06` `M` `native/platforms/macos-arm64.json`
- `S06` `M` `dev/packaging/native/layout.py`
- `S06` `A` `dev/packaging/native/macos_bundle.py`
- `S06` `M` `native/cmake/distribution/CMakeLists.txt`
- `S06` `M` `native/cmake/InstallerFlow.cmake`
- `S06` `verify:` `codesign --verify --strict --deep Cadrumo.app` -> `pass`
- `S06` `verify:` `open -n Cadrumo.app (window opens, LaunchServices md.neve.cadrumo)` -> `pass`
- `S06` `by:` `vaultspec-high-executor`
- `S01` `M` `.gitignore
dev/packaging/native/platforms/posix.py
dev/packaging/native/platforms/tests/test_posix.py
native/cmake/BinaryDirectory.cmake
native/cmake/BuildLog.cmake
native/cmake/BuildPaths.cmake
native/CONTRACT.md`
- `S01` `verify:` `cmake --preset macos-arm64 with the macos-arm64 user-preset inputs` -> `pass`
- `S04` `M` `native/CMakeLists.txt
native/desktop/scripts/backend-snapshot.mjs
native/desktop/src-tauri/Cargo.toml
native/desktop/src-tauri/src/agent/person.rs
native/desktop/src-tauri/src/agent/supervisor.rs
native/desktop/src-tauri/src/app.rs
native/desktop/src-tauri/src/environment.rs
native/desktop/src-tauri/src/launch.rs
native/desktop/src-tauri/src/manager.rs
native/desktop/src-tauri/src/manager/tests.rs
native/desktop/src-tauri/src/role.rs
native/desktop/src-tauri/src/shell/settle.rs
native/desktop/src-tauri/src/shell/sign_in/mod.rs
native/desktop/src-tauri/src/shell/sign_in/process.rs
native/desktop/src-tauri/src/shell/single_instance/mod.rs
native/desktop/src-tauri/src/shell/single_instance/posix.rs
native/desktop/src-tauri/src/shell/user_profile.rs
native/desktop/tests/backend-snapshot.test.mjs
native/interpreter_host/build.rs
native/interpreter_host/Cargo.toml
native/interpreter_host/src/lib.rs
native/interpreter/posix/host.c
native/manager/src/macos.rs
native/manager/src/macos/desktop_host.rs
native/manager/src/macos/ipc.rs
native/manager/src/main.rs`
- `S04` `verify:` `desktop GUI launch on macOS: window, single-instance handoff, runtime ready, clean Cmd+Q` -> `pass`
- `S08` `M` `native/application/src/canonical_json.rs
native/application/src/lib.rs
native/application/src/runtime_client.rs
native/application/src/view_stream.rs
native/application/src/view_stream/attach.rs
native/application/src/view_stream/lane.rs
native/desktop/src-tauri/src/agent/person.rs
native/desktop/src-tauri/src/agent/recovery.rs
native/desktop/src-tauri/src/agent/runner.rs
native/desktop/src-tauri/src/app.rs
native/desktop/src-tauri/src/main.rs
native/desktop/src-tauri/src/shell/sign_in/mod.rs
native/desktop/src-tauri/src/shell/sign_in/process.rs
native/desktop/src-tauri/src/shell/sign_in/watch.rs
native/desktop/src-tauri/src/startup_logging.rs
native/desktop/src-tauri/src/terminal/console.rs
native/desktop/src-tauri/src/terminal/session.rs
native/desktop/src-tauri/src/terminal/tests.rs
native/platform/src/account.rs
native/platform/src/keychain.rs
native/platform/src/keychain/tests.rs
native/platform/src/lib.rs
native/platform/src/process_scope.rs
native/platform/src/runtime_connect.rs
native/platform/src/runtime_pipe.rs
native/platform/src/runtime_socket.rs
native/platform/src/runtime_socket/tests.rs
native/platform/src/transport.rs
src/cadrumo_runtime/adapters/macos_process.py
src/cadrumo_runtime/adapters/service_verification.py
src/cadrumo_runtime/adapters/tests/test_macos_process.py
src/cadrumo_runtime/adapters/tests/test_macos_worker_containment.py
src/cadrumo_runtime/adapters/tests/test_worker_storage_environment.py
src/cadrumo_runtime/adapters/worker_environment.py
src/cadrumo_runtime/host/desktop_holder_identity.py
src/cadrumo_runtime/host/tests/test_desktop_holder_ancestry.py
src/cadrumo_runtime/host/tests/test_desktop_window_holder_macos.py
src/cadrumo_runtime/host/tests/test_desktop_window_holder.py`
- `S08` `verify:` `dev/runtime_lifecycle/native_client_live.py against the real Python runtime on macOS` -> `pass`

## Notes

- `S03` Baseline 396 failures reduced to 15 on rerun; remaining platform and in-progress failures fixed or already fixed by concurrent sessions; Chromium provisioned (581 MB)
- `S05` payload stage built by a parallel session's app-payload run in the shared build dir; relocation edits owned by that session
