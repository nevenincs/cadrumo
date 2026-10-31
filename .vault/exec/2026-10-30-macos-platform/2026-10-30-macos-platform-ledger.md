---
tags:
  - '#exec'
  - '#macos-platform'
date: '2026-10-30'
modified: '2026-10-31'
body_schema: 'body-v2'
body_hash: 'sha256:e48a391b44f64cfde1786d70d9aabb22db96f66b27379377d30c77a2eca26fa6'
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
- `S09` `M` `native/desktop/src-tauri/src/terminal/tests/live.rs`
- `S09` `M` `dev/packaging/native/tests/stand_in_launch.py`
- `S09` `M` `dev/packaging/native/release_image_scan.py`
- `S09` `M` `dev/packaging/tests/test_native_storage_environment_contract.py`
- `S09` `verify:` `pytest launch probe, storage vectors, contract, release scan, core storage_environment` -> `pass`
- `S09` `verify:` `ctest platform resolver/invocation/fmt/clippy, manager fmt, application fmt/clippy, desktop fmt, desktop clippy-backend` -> `pass`
- `S09` `M` `dev/packaging/native/generate.py
dev/packaging/tests/test_native_storage_environment_contract.py
native/application/src/provisioning/installation.rs
native/cmake/DesktopRust.cmake
native/cmake/Rust.cmake
native/CONTRACT.md
native/desktop/src-tauri/src/manager.rs
native/desktop/src-tauri/src/startup_logging.rs
native/manager/src/installation.rs
native/manager/src/installed.rs
native/manager/src/supervision/environment.rs
native/manager/tests/environment.rs
native/platform/src/conformance_tests.rs
native/platform/src/lib.rs
native/platform/src/posix_tests.rs
native/platform/src/storage.rs`
- `S09` `verify:` `ctest -C Debug -R platform|manager|application` -> `pass`
- `S10` `M` `native/CONTRACT.md
native/manager/src/supervision/launch.rs
native/manager/src/supervision/supervisor.rs`
- `S10` `verify:` `manager.rust SIGKILL-host containment test` -> `pass`
- `S12` `M` `dev/packaging/native/tests/test_transport_contract.py`
- `S12` `M` `dev/packaging/native/transport_contract.py`
- `S12` `M` `native/CONTRACT.md`
- `S12` `A` `native/application/src/instance_scope.rs`
- `S12` `M` `native/application/src/lib.rs`
- `S12` `M` `native/desktop/src-tauri/src/shell/single_instance/mod.rs`
- `S12` `M` `native/desktop/src-tauri/src/shell/single_instance/posix.rs`
- `S12` `M` `native/manager/Cargo.lock`
- `S12` `M` `native/manager/Cargo.toml`
- `S12` `M` `native/manager/src/cutover_coordinator.rs`
- `S12` `M` `native/manager/src/cutover_parent.rs`
- `S12` `M` `native/manager/src/desktop_host.rs`
- `S12` `M` `native/manager/src/installation.rs`
- `S12` `M` `native/manager/src/ipc/windows.rs`
- `S12` `M` `native/manager/src/macos/desktop_host.rs`
- `S12` `M` `native/manager/src/macos/ipc.rs`
- `S12` `M` `native/manager/src/main.rs`
- `S12` `M` `native/manager/src/session/instance.rs`
- `S12` `M` `native/manager/src/windows_lifecycle.rs`
- `S12` `M` `native/manager/tests/session_ownership.rs`
- `S12` `M` `native/platform/src/storage.rs`
- `S12` `M` `src/cadrumo/core/connection_transport.py`
- `S12` `M` `.vault/adr/2026-10-04-desktop-shell-adr.md`
- `S12` `M` `.vault/adr/2026-10-04-runtime-manager-architecture-adr.md`
- `S12` `M` `.vault/adr/2026-10-12-runtime-manager-architecture-caller-owned-root-adr.md`
- `S12` `M` `.vault/adr/2026-10-08-canonical-environment-darwin-transport-adr.md`
- `S12` `verify:` `ctest application.rust platform.resolver manager.rust manager.supervision` -> `pass`
- `S12` `verify:` `ctest fmt and clippy for platform, manager, application and desktop, manager.fixture.clippy, application.features.clippy` -> `pass`
- `S12` `verify:` `build.sh Debug desktop-host-unit-test and desktop-host-unit-clippy` -> `pass`
- `S12` `verify:` `pytest test_transport_contract.py test_connection_transport.py test_generator_imports.py` -> `pass`
- `S13` `M` `native/application/src/diagnostics/lifecycle.rs`
- `S13` `M` `native/application/src/diagnostics/logging.rs`
- `S13` `M` `native/application/src/lib.rs`
- `S13` `M` `native/application/src/shutdown.rs`
- `S13` `M` `native/CONTRACT.md`
- `S13` `M` `native/desktop/src-tauri/src/main.rs`
- `S13` `M` `native/desktop/src-tauri/src/role.rs`
- `S13` `M` `native/desktop/src-tauri/src/shell/single_instance/mod.rs`
- `S13` `M` `native/desktop/src-tauri/src/startup_logging.rs`
- `S13` `M` `native/desktop/src-tauri/src/startup_outcome.rs`
- `S13` `M` `native/desktop/src-tauri/src/startup.rs`
- `S13` `M` `native/manager/src/desktop_host.rs`
- `S13` `M` `native/manager/src/diagnostics.rs`
- `S13` `M` `native/manager/src/macos/desktop_host.rs`
- `S13` `M` `native/manager/src/supervision/exit.rs`
- `S13` `M` `native/manager/src/supervision/supervisor.rs`
- `S13` `M` `native/manager/tests/supervision.rs`
- `S13` `verify:` `build.sh Debug desktop-host-unit-test` -> `pass`
- `S13` `verify:` `ctest -C Debug -R manager.supervision` -> `pass`
- `S14` `M` `src/cadrumo_runtime/host/profile_connection_drain.py`
- `S14` `M` `src/cadrumo_runtime/host/terminated_operations.py`
- `S14` `M` `src/cadrumo_runtime/host/tests/test_runtime_drain.py`
- `S14` `M` `native/application/src/shutdown.rs`
- `S14` `M` `native/application/src/diagnostics/helper.rs`
- `S14` `M` `native/desktop/src-tauri/Cargo.toml`
- `S14` `M` `native/desktop/src-tauri/src/app.rs`
- `S14` `M` `native/desktop/src-tauri/src/main.rs`
- `S14` `M` `native/desktop/src-tauri/src/logs/severity.rs`
- `S14` `M` `native/desktop/src-tauri/src/shell/setup/reports.rs`
- `S14` `M` `native/desktop/src-tauri/src/shell/setup/reports_tests.rs`
- `S14` `M` `native/desktop/src-tauri/src/shell/sign_in/mod.rs`
- `S14` `M` `native/desktop/src-tauri/src/shell/sign_in/observation.rs`
- `S14` `M` `native/desktop/src-tauri/src/shell/sign_in/process.rs`
- `S14` `M` `native/desktop/src-tauri/src/shell/sign_in/watch.rs`
- `S14` `M` `native/desktop/src-tauri/src/shell/user_profile.rs`
- `S14` `M` `native/desktop/frontend/src/App.tsx`
- `S14` `M` `native/desktop/frontend/src/dev/scenarioHost.ts`
- `S14` `M` `native/desktop/frontend/src/ipc/contract.ts`
- `S14` `M` `native/desktop/frontend/src/shell/host.ts`
- `S14` `M` `native/desktop/frontend/src/shell/tauriHost.ts`
- `S14` `M` `dev/locales/desktop_interface_keys.py`
- `S14` `M` `src/cadrumo/locales/en/common.yml`
- `S14` `M` `src/cadrumo/locales/es/common.yml`
- `S14` `M` `src/cadrumo/locales/ca/common.yml`
- `S14` `M` `src/cadrumo/locales/hu/common.yml`
- `S14` `M` `.vault/adr/2026-10-04-desktop-shell-adr.md`
- `S14` `M` `.vault/adr/2026-10-04-runtime-manager-architecture-supervisor-contract-adr.md`
- `S14` `A` `src/cadrumo_runtime/host/tests/test_drained_worker_settlement.py`
- `S14` `A` `native/desktop/src-tauri/src/close_outcome.rs`
- `S14` `A` `native/desktop/frontend/tests/scenarios/previous-close.spec.ts`
- `S14` `verify:` `pytest runtime drain, session-end, terminated-owner tests` -> `pass`
- `S14` `verify:` `desktop-host-unit-test` -> `pass`
- `S14` `verify:` `desktop-host-unit-clippy` -> `pass`
- `S14` `verify:` `ctest application.rust application.clippy application.fmt desktop.fmt` -> `pass`
- `S14` `verify:` `desktop-frontend-check` -> `pass`
- `S14` `verify:` `desktop-frontend-test scenarios/previous-close` -> `pass`
- `S14` `verify:` `lint-imports` -> `pass`
- `S14` `by:` `vaultspec-high-executor`
- `S11` `M` `native/CONTRACT.md`
- `S11` `M` `native/desktop/frontend/src/components/Titlebar.tsx`
- `S11` `M` `native/desktop/frontend/src/dev/scenarioHost.ts`
- `S11` `M` `native/desktop/frontend/src/ipc/contract.ts`
- `S11` `M` `native/desktop/frontend/src/styles/titlebar.css`
- `S11` `M` `native/desktop/frontend/src/styles/tokens.css`
- `S11` `M` `native/desktop/frontend/tests/window-controls.spec.ts`
- `S11` `M` `native/desktop/src-tauri/src/app.rs`
- `S11` `M` `native/desktop/src-tauri/src/shell/window_controls.rs`
- `S11` `M` `native/interpreter/posix/host.c`
- `S11` `verify:` `desktop-frontend window-controls spec and packaged window screenshot` -> `pass`
- `S16` `M` `native/desktop/src-tauri/src/shell/single_instance/mod.rs`
- `S16` `M` `native/desktop/src-tauri/src/shell/single_instance/posix.rs`
- `S16` `M` `native/manager/src/macos/ipc.rs`
- `S16` `M` `native/manager/src/macos/ipc/socket.rs`
- `S16` `M` `native/manager/src/session/instance.rs`
- `S16` `M` `native/manager/tests/session_ownership.rs`
- `S16` `M` `native/platform/src/transport.rs`
- `S16` `M` `src/cadrumo_client/transport/tests/account_transport.py`
- `S16` `M` `src/cadrumo_client/transport/tests/test_isolated_transport_namespace.py`
- `S16` `M` `src/cadrumo_runtime/adapters/tests/test_darwin_transport.py`
- `S16` `M` `src/cadrumo_runtime/adapters/tests/test_posix.py`
- `S16` `M` `src/cadrumo_runtime/host/tests/conftest.py`
- `S16` `M` `src/cadrumo/core/tests/test_storage_fingerprint_participation_gate.py`
- `S16` `M` `src/cadrumo/tests/process_support.py`
- `S16` `verify:` `build.sh Debug desktop-host-unit-test (702) with real transport dir unchanged` -> `pass`
- `S15` `M` `dev/packaging/native/agent.py`
- `S15` `M` `dev/packaging/native/distribution_prepare.py`
- `S15` `M` `dev/packaging/native/installation_currency.py`
- `S15` `M` `dev/packaging/native/installation_plan.py`
- `S15` `M` `dev/packaging/native/installation.py`
- `S15` `M` `dev/packaging/native/macos_bundle.py`
- `S15` `M` `dev/packaging/native/platforms/posix_images.py`
- `S15` `M` `dev/packaging/native/tests/test_macos_bundle.py`
- `S15` `M` `dev/packaging/tests/test_native_installation.py`
- `S15` `M` `native/cmake/distribution/CMakeLists.txt`
- `S15` `M` `native/cmake/distribution/MacosBundleSeal.cmake.in`
- `S15` `M` `native/cmake/distribution/MacosBundleVerify.cmake.in`
- `S15` `M` `native/CONTRACT.md`
- `S15` `verify:` `CPack pre-build runtime-role gate and codesign --verify --deep --strict on stage, DMG, ZIP` -> `pass`
- `S07` `M` `dev/packaging/native/macos_bundle.py`
- `S07` `M` `dev/packaging/native/tests/test_macos_bundle.py`
- `S07` `M` `native/CONTRACT.md`
- `S07` `verify:` `packaged Cadrumo.app: runtime ready, Apple Event and SIGTERM clean drain, SIGKILL containment, handoff record` -> `pass`

## Notes

- `S03` Baseline 396 failures reduced to 15 on rerun; remaining platform and in-progress failures fixed or already fixed by concurrent sessions; Chromium provisioned (581 MB)
- `S05` payload stage built by a parallel session's app-payload run in the shared build dir; relocation edits owned by that session
- `S09` manager rust/supervision/clippy blocked by foreign uncommitted unsafe blocks in launch.rs; application diagnostics retry test fails, unrelated; bundle.environment-launch not rerun for disk
- `S12` Windows dispatch, cutover, session mutex, pipe and desktop host changes were not compiled or run: no Windows target on this Mac.
- `S12` macOS process tests still claim in the real per-user Darwin transport directory, as the existing ones do; Step S16 isolates it.
- `S14` The Windows-only real-worker drain test `(test_runtime_drain.py)` was updated for the new terminal outcome but not run here; no packaged GUI launch verified SIGTERM end to end
