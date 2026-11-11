---
tags:
  - '#exec'
  - '#local-ai-on-demand-server'
date: '2026-11-11'
modified: '2026-11-11'
body_schema: 'body-v2'
body_hash: 'sha256:64f2bb79c3982a6f8c44e8d52d0ec77fe6d920d3896f94f2f5e8d789f13dad52'
related:
  - "[[2026-11-11-local-ai-on-demand-server-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `local-ai-on-demand-server` ledger

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

- `S01` `M` `native/application/src/provisioning/local_ai/supervision.rs`
- `S01` `M` `native/application/src/provisioning/local_ai/supervision/tests.rs`
- `S01` `M` `native/application/src/provisioning/local_ai/llama_server/tests.rs`
- `S02` `M` `native/manager/src/supervision/local_ai.rs`
- `S02` `M` `native/manager/src/background.rs`
- `S02` `M` `native/manager/src/diagnostics.rs`
- `S02` `M` `native/application/src/diagnostics/lifecycle.rs`
- `S02` `M` `native/application/src/provisioning/local_ai/supervision.rs`
- `S02` `M` `native/desktop/src-tauri/src/logs/manager.rs`
- `S02` `M` `native/desktop/src-tauri/src/logs/severity.rs`
- `S03` `M` `native/manager/src/cutover_windows.rs`
- `S03` `M` `native/manager/src/desktop_host.rs`
- `S03` `M` `native/manager/src/ipc.rs`
- `S03` `M` `native/manager/src/ipc/windows.rs`
- `S03` `M` `native/manager/src/lifecycle.rs`
- `S03` `M` `native/manager/src/linux/ipc.rs`
- `S03` `M` `native/manager/src/macos/ipc.rs`
- `S03` `M` `native/manager/src/windows_lifecycle.rs`
- `S03` `verify:` `rustfmt --check` -> `pass`
- `S03` `verify:` `branch_gate_delta` -> `pass`

## Notes

- `S01` cargo tests not run here: native builds are root-only; pending DESKTOP
- `S02` cargo tests not run here: native builds are root-only; pending DESKTOP
- `S03` cargo not run here (native builds root-only); pending DESKTOP manager.rust: ipc::windows `only_the_agent_service_a_desktop_started_may_demand_the_local_ai_server,` ipc `a_demand_carries_no_identity`
