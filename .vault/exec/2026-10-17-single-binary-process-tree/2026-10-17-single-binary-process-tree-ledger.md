---
tags:
  - '#exec'
  - '#single-binary-process-tree'
date: '2026-10-17'
modified: '2026-10-17'
body_schema: 'body-v2'
body_hash: 'sha256:23fa3983407e402472befa4e754e76b3a23a8854d2e6a16ebcf265a28d0bbb30'
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

## Notes

- `S01` pytest dev/packaging: 1969 passed, 1 pre-existing failure `test_discovered_live_var_members_cover_the_readiness_gate_inputs` outside this change
- `S01` session watch helper (cadrumo-runtime.exe) still shows as its own row until S02; WebView2 children show under the WebView2 Manager row
