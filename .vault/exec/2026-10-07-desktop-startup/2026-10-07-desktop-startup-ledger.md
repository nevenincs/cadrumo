---
tags:
  - '#exec'
  - '#desktop-startup'
date: '2026-10-07'
modified: '2026-10-13'
body_schema: 'body-v2'
body_hash: 'sha256:1297cac821cd7b8b9a788634a8c77db23c6abd967453eb465b15e3a91a70c8aa'
related:
  - "[[2026-10-07-desktop-startup-plan]]"
---

# `desktop-startup` ledger

## Changes

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
