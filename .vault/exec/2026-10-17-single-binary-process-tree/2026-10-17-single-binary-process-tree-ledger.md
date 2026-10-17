---
tags:
  - '#exec'
  - '#single-binary-process-tree'
date: '2026-10-17'
modified: '2026-10-17'
body_schema: 'body-v2'
body_hash: 'sha256:b21b773411dcac7c314d1a542c3cc48b9f8fadb79adcf8867f1c960452f0013e'
related:
  - "[[2026-10-17-single-binary-process-tree-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `single-binary-process-tree` ledger

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

## Notes

- `S01` pytest dev/packaging: 1969 passed, 1 pre-existing failure `test_discovered_live_var_members_cover_the_readiness_gate_inputs` outside this change
- `S01` session watch helper (cadrumo-runtime.exe) still shows as its own row until S02; WebView2 children show under the WebView2 Manager row
- `S02` Task Manager groups only process trees present when it opens; processes started while it is open get their own rows, so grouping is judged in a freshly opened Task Manager. WebView2 stays under its own Microsoft row. Roles run on Windows only until S08.
- `S02` desktop-session admission still matches by image and parent image only; once runtime workers run as cadrumo.exe (S03) they would pass it, so admission must bind role and invocation or parent incarnation before S03 lands. `no_error_records` fails on refusal boundaries logged at ERROR since 262e873ce3, outside this change.
