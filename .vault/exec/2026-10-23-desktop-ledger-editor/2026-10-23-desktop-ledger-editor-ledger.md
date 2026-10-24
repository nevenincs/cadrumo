---
tags:
  - '#exec'
  - '#desktop-ledger-editor'
date: '2026-10-23'
modified: '2026-10-24'
body_schema: 'body-v2'
body_hash: 'sha256:8407d29e8294d4296f945ec8645b4e1c1bba9d5a90401d490372c87015e57d5f'
related:
  - "[[2026-10-23-desktop-ledger-editor-plan]]"
---

# `desktop-ledger-editor` ledger

## Changes

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
- `S01` `M` `native/desktop/src-tauri/src/shell/ledger/mod.rs`
- `S01` `M` `native/desktop/src-tauri/src/shell/ledger/tests.rs`
- `S01` `M` `.vault/adr/2026-10-23-desktop-ledger-editor-adr.md`
- `S01` `verify:` `desktop-host-unit-test` -> `pass`
- `S01` `verify:` `desktop-host-unit-clippy` -> `pass`
- `S05` `A` `native/desktop/frontend/src/components/ui/data-grid.tsx`
- `S05` `A` `native/desktop/frontend/src/components/ui/dataGridModel.ts`
- `S05` `A` `native/desktop/frontend/src/components/ui/combobox.tsx`
- `S05` `A` `native/desktop/frontend/src/components/ui/sheet.tsx`
- `S05` `A` `native/desktop/frontend/src/components/ui/filter-chip.tsx`
- `S05` `A` `native/desktop/frontend/src/components/ui/data-grid.stories.tsx`
- `S05` `A` `native/desktop/frontend/src/components/ui/combobox.stories.tsx`
- `S05` `A` `native/desktop/frontend/src/components/ui/sheet.stories.tsx`
- `S05` `A` `native/desktop/frontend/src/components/ui/filter-chip.stories.tsx`
- `S05` `M` `native/desktop/frontend/src/components/ui/icon.tsx`
- `S05` `M` `native/desktop/frontend/src/components/ui/cn.ts`
- `S05` `M` `native/desktop/frontend/src/components/ui/popover.tsx`
- `S05` `M` `native/desktop/frontend/src/components/ui/dialog.tsx`
- `S05` `M` `native/desktop/frontend/src/styles/tokens.css`
- `S05` `M` `native/desktop/frontend/src/styles/theme.css`
- `S05` `M` `native/desktop/frontend/src/components/calendar/calendarMarks.ts`
- `S05` `M` `native/desktop/frontend/src/dev/catalogue/Foundations.stories.tsx`
- `S05` `A` `native/desktop/frontend/primitives.html`
- `S05` `A` `native/desktop/frontend/src/dev/primitives/main.tsx`
- `S05` `A` `native/desktop/frontend/src/dev/primitives/DataGridHarness.tsx`
- `S05` `A` `native/desktop/frontend/src/dev/primitives/CompanionsHarness.tsx`
- `S05` `A` `native/desktop/frontend/src/dev/primitives/gridSample.ts`
- `S05` `M` `native/desktop/frontend/README.md`
- `S05` `verify:` `npx tsc --noEmit` -> `pass`
- `S05` `verify:` `npx eslint <touched files>` -> `pass`
- `S05` `verify:` `npx prettier --check <touched files>` -> `pass`
- `S05` `verify:` `node --test dev/eslint/tests/` -> `pass`
- `S05` `by:` `vaultspec-high-executor`
- `S06` `A` `native/desktop/frontend/tests/data-grid.spec.ts`
- `S06` `A` `native/desktop/frontend/tests/scenarios/data-grid.spec.ts`
- `S06` `verify:` `npx playwright test tests/data-grid.spec.ts (19 pure tests, server-free config)` -> `pass`
- `S06` `verify:` `npx playwright test tests/scenarios/data-grid.spec.ts (16 tests on /primitives.html, dev server started and stopped by this run)` -> `pass`
- `S06` `verify:` `npx playwright test tests/scenarios/accessibility.spec.ts design-system.spec.ts keyboard.spec.ts` -> `pass`
- `S06` `verify:` `npx tsc --noEmit; npx eslint; npx prettier --check` -> `pass`
- `S06` `by:` `vaultspec-high-executor`

## Notes

- `S04` Playwright scenario suite not run here: it starts the fixed-port development and preview servers; the Ledger page's scenario tests belong to P04.S16.
- `S01` Follow-up correction: results reach the window with file names, not paths (ADR amendment 2026-10-24)
