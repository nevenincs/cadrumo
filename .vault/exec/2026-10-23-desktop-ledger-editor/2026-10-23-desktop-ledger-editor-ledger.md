---
tags:
  - '#exec'
  - '#desktop-ledger-editor'
date: '2026-10-23'
modified: '2026-10-24'
body_schema: 'body-v2'
body_hash: 'sha256:c6ef3d7dac1c94fd66d1418444d52c9eddc93c64ddf07073e9f8cde2712a4376'
related:
  - "[[2026-10-23-desktop-ledger-editor-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `desktop-ledger-editor` ledger

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

- `S01` `A` `native/desktop/src-tauri/src/shell/relay.rs`
- `S01` `A` `native/desktop/src-tauri/src/shell/ledger/mod.rs`
- `S01` `A` `native/desktop/src-tauri/src/shell/ledger/admitted.rs`
- `S01` `A` `native/desktop/src-tauri/src/shell/ledger/tests.rs`
- `S01` `A` `native/desktop/src-tauri/src/shell/ledger/relay_contracts.py`
- `S01` `A` `native/desktop/src-tauri/src/shell/ledger/relay_contracts.json`
- `S01` `M` `native/desktop/src-tauri/src/shell/user_profile.rs`
- `S01` `M` `native/desktop/src-tauri/src/shell/mod.rs`
- `S01` `M` `native/desktop/src-tauri/src/agent/person.rs`
- `S01` `M` `native/desktop/src-tauri/src/agent/mod.rs`
- `S01` `M` `native/desktop/src-tauri/src/app.rs`
- `S01` `M` `native/desktop/CMakeLists.txt`
- `S01` `verify:` `tauri.mjs test-unit ledger` -> `pass`
- `S01` `verify:` `tauri.mjs test-unit shell::user_profile` -> `pass`
- `S01` `verify:` `tauri.mjs test-unit app::tests` -> `pass`
- `S01` `verify:` `tauri.mjs test-unit agent::person` -> `pass`
- `S01` `verify:` `tauri.mjs clippy-backend` -> `pass`
- `S01` `verify:` `relay_contracts.py --check` -> `pass`
- `S01` `verify:` `ruff check and format --check relay_contracts.py` -> `pass`
- `S01` `by:` `vaultspec-high-executor`
- `S02` `A` `native/desktop/src-tauri/src/shell/ledger/files.rs`
- `S02` `M` `native/desktop/src-tauri/src/shell/ledger/mod.rs`
- `S02` `M` `native/desktop/src-tauri/src/shell/ledger/tests.rs`
- `S02` `M` `native/desktop/src-tauri/src/shell/relay.rs`
- `S02` `M` `native/desktop/src-tauri/src/agent/person.rs`
- `S02` `verify:` `tauri.mjs test-unit ledger` -> `pass`
- `S02` `verify:` `tauri.mjs test-unit agent::` -> `pass`
- `S02` `verify:` `tauri.mjs test-unit shell::user_profile` -> `pass`
- `S02` `verify:` `tauri.mjs test-unit app::tests` -> `pass`
- `S02` `verify:` `tauri.mjs clippy-backend` -> `pass`
- `S02` `by:` `vaultspec-high-executor`
- `S03` `A` `native/desktop/frontend/src/shell/ledger.ts`
- `S03` `A` `native/desktop/frontend/src/shell/tauriLedger.ts`
- `S03` `M` `native/desktop/frontend/src/shell/tauriHost.ts`
- `S03` `M` `native/desktop/frontend/src/shell/host.ts`
- `S03` `M` `native/desktop/frontend/src/ipc/contract.ts`
- `S03` `M` `native/desktop/frontend/eslint.config.js`
- `S03` `M` `native/desktop/frontend/README.md`
- `S03` `M` `native/desktop/src-tauri/src/shell/ledger/relay_contracts.py`
- `S03` `verify:` `npx tsc --noEmit` -> `pass`
- `S03` `verify:` `npx eslint on touched files` -> `pass`
- `S03` `verify:` `npx prettier --check on touched files` -> `pass`
- `S03` `verify:` `relay_contracts.py --check (and a deliberate mirror drift refused)` -> `pass`
- `S03` `verify:` `ruff check and format --check relay_contracts.py` -> `pass`
- `S03` `by:` `vaultspec-high-executor`
- `S04` `A` `native/desktop/frontend/src/dev/ledgerFixture.ts`
- `S04` `A` `native/desktop/frontend/src/dev/fixtures/ledger.ts`
- `S04` `M` `native/desktop/frontend/src/dev/scenarioHost.ts`
- `S04` `M` `native/desktop/frontend/src/dev/scenarios.ts`
- `S04` `M` `native/desktop/frontend/src/dev/main.tsx`
- `S04` `M` `native/desktop/frontend/README.md`
- `S04` `verify:` `npx tsc --noEmit` -> `pass`
- `S04` `verify:` `npx eslint on touched files` -> `pass`
- `S04` `verify:` `npx prettier --check on touched files` -> `pass`
- `S04` `verify:` `scratch semantics probe of the scenario ledger (esbuild bundle run in node, 31 checks)` -> `pass`
- `S04` `by:` `vaultspec-high-executor`

## Notes

- `S04` Playwright scenario suite not run here: it starts the fixed-port development and preview servers; the Ledger page's scenario tests belong to P04.S16.
