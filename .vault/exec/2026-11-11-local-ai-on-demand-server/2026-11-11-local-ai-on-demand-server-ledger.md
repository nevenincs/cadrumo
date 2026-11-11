---
tags:
  - '#exec'
  - '#local-ai-on-demand-server'
date: '2026-11-11'
modified: '2026-11-11'
body_schema: 'body-v2'
body_hash: 'sha256:60eb447402077b8a20f28ff573a6e2326f03ce70be6d48f7f13dc49cd3429c1e'
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
- `S04` `M` `dev/locales/desktop_interface_keys.py`
- `S04` `M` `native/application/src/provisioning/engine.rs`
- `S04` `M` `native/application/src/provisioning/engine/tests.rs`
- `S04` `M` `native/application/src/provisioning/local_ai/mod.rs`
- `S04` `M` `native/application/src/provisioning/local_ai/models.rs`
- `S04` `M` `native/application/src/provisioning/local_ai/models/tests.rs`
- `S04` `M` `native/application/src/provisioning/local_ai/program.rs`
- `S04` `M` `native/application/src/provisioning/state.rs`
- `S04` `M` `native/desktop/frontend/src/components/setup/setupWords.ts`
- `S04` `M` `native/desktop/frontend/src/ipc/componentSetup.ts`
- `S04` `M` `native/desktop/frontend/tests/setup-words.spec.ts`
- `S04` `M` `native/desktop/src-tauri/src/shell/setup/components.rs`
- `S04` `M` `native/desktop/src-tauri/src/shell/setup/wire.rs`
- `S04` `M` `src/cadrumo/locales/ca/common.yml`
- `S04` `M` `src/cadrumo/locales/en/common.yml`
- `S04` `M` `src/cadrumo/locales/es/common.yml`
- `S04` `M` `src/cadrumo/locales/hu/common.yml`
- `S04` `verify:` `rustfmt --check` -> `pass`
- `S04` `verify:` `prettier eslint tsc` -> `pass`
- `S04` `verify:` `pytest dev/locales/tests` -> `pass`
- `S04` `verify:` `branch_gate_delta` -> `pass`
- `S05` `M` `native/application/src/provisioning/engine.rs`
- `S05` `M` `native/application/src/provisioning/engine/tests.rs`
- `S05` `M` `native/application/src/provisioning/local_ai/mod.rs`
- `S05` `M` `native/application/src/provisioning/local_ai/models/tests.rs`
- `S05` `M` `native/application/src/provisioning/local_ai/program/tests.rs`
- `S05` `M` `native/application/src/provisioning/activity.rs`
- `S05` `M` `native/desktop/src-tauri/src/shell/setup/components.rs`
- `S05` `M` `native/desktop/src-tauri/src/shell/setup/components_tests.rs`
- `S05` `verify:` `rustfmt --check` -> `pass`
- `S05` `verify:` `branch_gate_delta` -> `pass`

## Notes

- `S01` cargo tests not run here: native builds are root-only; pending DESKTOP
- `S02` cargo tests not run here: native builds are root-only; pending DESKTOP
- `S03` cargo not run here (native builds root-only); pending DESKTOP manager.rust: ipc::windows `only_the_agent_service_a_desktop_started_may_demand_the_local_ai_server,` ipc `a_demand_carries_no_identity`
- `S04` cargo and Playwright setup-words not run here (root-only); pending DESKTOP staged verification with S01-S06
- `S03` coordinator review: parent must be the admitted desktop process (PID + creation time), not any desktop-image process; cargo pending DESKTOP staged verification
- `S05` cargo, clippy and ctest pending: DESKTOP verifies staged in root; `llama_server::presentation` is left with only test callers `(live_package.rs,` `llama_server/tests.rs),` flagged for S06 reuse or removal
