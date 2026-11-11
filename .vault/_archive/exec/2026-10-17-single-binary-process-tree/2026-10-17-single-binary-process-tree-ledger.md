---
tags:
  - '#exec'
  - '#single-binary-process-tree'
date: '2026-10-17'
modified: '2026-10-21'
body_schema: 'body-v2'
body_hash: 'sha256:ea6a73a92d411d93c2711c3cd8f49e24e93ff5c3ceb218807982daca893b6da7'
related:
  - "[[2026-10-17-single-binary-process-tree-plan]]"
---

# `single-binary-process-tree` ledger

## Changes

- `S01` `M` `native/application/src/lib.rs`
- `S01` `A` `native/application/src/role.rs`
- `S01` `M` `native/desktop/scripts/backend-snapshot.mjs`
- `S01` `M` `native/desktop/src-tauri/Cargo.lock`
- `S01` `M` `native/desktop/src-tauri/Cargo.toml`
- `S01` `M` `native/desktop/src-tauri/src/main.rs`
- `S01` `A` `native/desktop/src-tauri/src/role.rs`
- `S01` `M` `native/desktop/tests/backend-snapshot.test.mjs`
- `S01` `M` `native/interpreter/launch_profile.h`
- `S01` `M` `native/interpreter/posix/host.c`
- `S01` `M` `native/interpreter/posix/tests/invocation.c`
- `S01` `M` `native/interpreter/windows/host.c`
- `S01` `A` `native/interpreter_host/Cargo.lock`
- `S01` `A` `native/interpreter_host/Cargo.toml`
- `S01` `A` `native/interpreter_host/build.rs`
- `S01` `A` `native/interpreter_host/src/lib.rs`
- `S01` `M` `native/manager/src/supervision/environment.rs`
- `S01` `M` `native/manager/src/supervision/launch.rs`
- `S01` `M` `native/manager/tests/runtime_identity.rs`
- `S01` `M` `dev/packaging/native/linux_desktop_runtime.py`
- `S01` `M` `dev/packaging/native/tests/test_agent_image.py`
- `S01` `verify:` `cmake --build --preset debug --target app-payload` -> `pass`
- `S01` `verify:` `cargo test (application role, interpreter_host, manager supervision)` -> `pass`
- `S01` `verify:` `pytest dev/packaging` -> `fail`
- `S01` `verify:` `Task Manager capture: cadrumo.exe --role runtime nested under Cadrumo (2)` -> `pass`
- `S02` `M` `native/application/src/role.rs`
- `S02` `M` `native/application/src/child.rs`
- `S02` `M` `native/desktop/src-tauri/src/shell/sign_in/mod.rs`
- `S02` `verify:` `cargo test application role and child` -> `pass`
- `S02` `verify:` `run-backend.ps1 -Filter shell::sign_in 50 tests` -> `pass`
- `S02` `verify:` `run-backend.ps1 -Mode Clippy` -> `pass`
- `S02` `verify:` `live stage/Debug: session watch runs as cadrumo.exe --role runtime session watch under the window` -> `pass`
- `S02` `verify:` `fresh Task Manager shows one cadrumo.exe row of 162.9 MB covering window, runtime and session watch` -> `pass`
- `S02` `M` `dev/packaging/native/service_descriptors.py`
- `S02` `A` `dev/packaging/tests/test_native_service_descriptors.py`
- `S02` `M` `dev/runtime_lifecycle/session_holder.py`
- `S02` `M` `dev/runtime_lifecycle/tests/test_session_holder.py`
- `S02` `verify:` `pytest test_native_service_descriptors.py and test_session_holder.py` -> `pass`
- `S02` `verify:` `concurrent_sessions_probe on stage/Debug: fan_in, cross_profile, race, sign_out and resume_race checks` -> `pass`
- `S02` `verify:` `concurrent_sessions_probe no_error_records` -> `fail`
- `S03` `M` `src/cadrumo_client/contracts/service_access.py`
- `S03` `M` `src/cadrumo_runtime/adapters/service_verification.py`
- `S03` `M` `src/cadrumo_runtime/adapters/tests/test_service_verification.py`
- `S03` `M` `src/cadrumo_runtime/host/profile_connection_services.py`
- `S03` `A` `src/cadrumo_runtime/host/tests/test_desktop_holder_ancestry.py`
- `S03` `M` `dev/packaging/native/service_descriptors.py`
- `S03` `M` `dev/packaging/tests/test_native_service_descriptors.py`
- `S03` `verify:` `pytest service verification, holder ancestry, service records, frontend matrix, contracts 225 tests` -> `pass`
- `S03` `verify:` `ty, pyrefly and basedpyright on changed modules` -> `pass`
- `S03` `verify:` `cmake app-payload debug` -> `pass`
- `S03` `verify:` `concurrent_sessions_probe stage/Debug with launch_arguments bound` -> `pass`
- `S03` `verify:` `backend_probe stage/Debug` -> `pass`
- `S03` `M` `native/interpreter/windows/host.c`
- `S03` `M` `native/application/src/role.rs`
- `S03` `M` `native/interpreter_host/src/lib.rs`
- `S03` `A` `src/cadrumo/core/package_interpreter.py`
- `S03` `A` `src/cadrumo/core/tests/test_package_interpreter.py`
- `S03` `M` `src/cadrumo/adapters/persistence/storage/custody/_kdf_process.py`
- `S03` `A` `src/cadrumo/adapters/persistence/storage/custody/tests/test_kdf_hosted_interpreter.py`
- `S03` `M` `src/cadrumo_runtime/adapters/profile_worker.py`
- `S03` `M` `dev/packaging/native/package_launch_smoke.py`
- `S03` `M` `dev/runtime_lifecycle/harness.py`
- `S03` `verify:` `cargo test application role and child` -> `pass`
- `S03` `verify:` `run-backend.ps1 -Mode Clippy with the linked host` -> `pass`
- `S03` `verify:` `pytest package interpreter, KDF hosted interpreter, KDF import graph, test_agent_image` -> `pass`
- `S03` `verify:` `lint-imports 25 contracts` -> `pass`
- `S03` `verify:` `cmake app-payload debug` -> `pass`
- `S03` `verify:` `ctest bundle.launch and bundle.health on Debug` -> `pass`
- `S03` `verify:` `live stage/Debug under the manager: workers, a worker KDF child and the runtime KDF child run as cadrumo.exe --role python` -> `pass`
- `S03` `verify:` `bundle.runtime-lifecycle on Debug 8 of 9` -> `fail`

## Notes

- `S01` pytest dev/packaging: 1969 passed, 1 pre-existing failure `test_discovered_live_var_members_cover_the_readiness_gate_inputs` outside this change
- `S01` session watch helper (cadrumo-runtime.exe) still shows as its own row until S02; WebView2 children show under the WebView2 Manager row
- `S02` Task Manager groups only process trees present when it opens; processes started while it is open get their own rows, so grouping is judged in a freshly opened Task Manager. WebView2 stays under its own Microsoft row. Roles run on Windows only until S08.
- `S02` desktop-session admission still matches by image and parent image only; once runtime workers run as cadrumo.exe (S03) they would pass it, so admission must bind role and invocation or parent incarnation before S03 lands. `no_error_records` fails on refusal boundaries logged at ERROR since 262e873ce3, outside this change.
- `S03` Admission part of S03 done; sys.executable re-entry for workers and the KDF child is still open.
- `S03` `test_exact_runtime_crash_manager_recovery_and_operation_state` fails in the full suite with `authentication_required` on Debug and on the Release baseline without this change (Release also fails `test_packaged_client_authentication_and_profile_scope);` alone it passes on both in about 632 s. The lifecycle driver had to be rebuilt; it predated S01. The standalone aeat and cadrumo-runtime images still start python.exe children, as they are operator programs.
