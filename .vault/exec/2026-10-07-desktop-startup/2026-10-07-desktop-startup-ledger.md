---
tags:
  - '#exec'
  - '#desktop-startup'
date: '2026-10-07'
modified: '2026-10-07'
body_schema: 'body-v2'
body_hash: 'sha256:e858b299d56e9e3f9b8ef1b4c251ddbef692d3f34a51640bee97a68ec00d62c6'
related:
  - "[[2026-10-07-desktop-startup-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `desktop-startup` ledger

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

- `S01` `M` `native/desktop/frontend/src/components/TerminalPane.tsx`
- `S01` `M` `native/desktop/frontend/src/shell/layout.ts`
- `S01` `M` `native/desktop/frontend/tests/desktop.spec.ts`
- `S01` `M` `native/desktop/frontend/tests/scenarios/keyboard.spec.ts`
- `S01` `M` `native/desktop/frontend/tests/scenarios/scenarios.spec.ts`
- `S01` `M` `native/desktop/frontend/tests/scenarios/touch.spec.ts`
- `S01` `verify:` `npx tsc --noEmit` -> `pass`
- `S01` `verify:` `scoped eslint and prettier` -> `pass`
- `S01` `verify:` `playwright desktop.spec.ts --project=product (26 tests)` -> `pass`
- `S02` `M` `dev/packaging/native/generate.py`
- `S02` `M` `dev/packaging/tests/test_native_storage_environment_contract.py`
- `S02` `M` `native/CMakeLists.txt`
- `S02` `M` `native/CONTRACT.md`
- `S02` `M` `native/platform/src/desktop.rs`
- `S02` `M` `native/platform/src/lib.rs`
- `S02` `M` `native/platform/src/storage.rs`
- `S02` `M` `native/desktop/src-tauri/src/main.rs`
- `S02` `M` `native/desktop/src-tauri/src/environment.rs`
- `S02` `M` `native/desktop/tests/headless.test.mjs`
- `S02` `M` `.vault/adr/2026-10-04-desktop-shell-adr.md`
- `S02` `verify:` `packaged environment checks (9 tests)` -> `pass`
- `S02` `verify:` `headless.test.mjs real GUI-subsystem Debug image` -> `pass`
- `S02` `verify:` `platform cargo test (39 tests)` -> `pass`
- `S02` `verify:` `native unit tests (167 tests)` -> `pass`
- `S02` `verify:` `native clippy -D warnings` -> `pass`
- `S02` `verify:` `canonical generator pytest (6 tests)` -> `pass`
- `S02` `verify:` `scoped rustfmt and git diff --check` -> `pass`
- `S03` `A` `.vault/audit/2026-10-07-desktop-startup-audit.md`
- `S03` `verify:` `integrated independent startup review` -> `pass`

## Notes

- `S01` Broader 208-test browser run: 201 passed and seven log-view scenarios failed during concurrent log and sign-in edits; focused immutable production-assets desktop suite passed.
- `S02` Test contract generated with current generator from installed package canonical Python defaults to avoid concurrent log-format cohort mismatch. Native preparation 390.9929ms vs Python query 1.5663107s; full output parity and no Environment child verified.
- `S02` Concurrent diagnostic compile errors required type annotations in `sign_in/process.rs` and terminal/session.rs plus ErrorKind formatting in logs/host.rs and RelativePath argument in manager.rs. Their unrelated work remains unstaged.
- `S02` Git index.lock held outside this task prevented checkpoint staging on two attempts; preserve other work and leave checkpoint uncommitted until lock is released.
- `S03` Session 1 visual/full-launch timing not measured; installed package untouched. Debug GUI-subsystem host built and real headless parity passed. Checkpoint commits deferred because another operation holds the worktree Git index.lock.
