---
tags:
  - '#exec'
  - '#cadrumo-windowmanager'
date: '2026-11-02'
modified: '2026-11-02'
body_schema: 'body-v2'
body_hash: 'sha256:21ee39e60c62eccaaaf29298d46a6f5493edceecca4a5cd5f3af19708884c1ac'
related:
  - "[[2026-11-02-cadrumo-windowmanager-plan]]"
---

# `cadrumo-windowmanager` ledger

## Changes

- `S01` `A` `native/desktop/frontend/src/shell/docking.ts`
- `S01` `M` `native/desktop/frontend/src/shell/layout.ts`
- `S01` `A` `native/desktop/frontend/tests/live/docking.unit.ts`
- `S01` `verify:` `node --test tests/live/docking.unit.ts` -> `pass`
- `S01` `verify:` `tsc --noEmit` -> `pass`
- `S01` `verify:` `eslint .` -> `pass`
- `S01` `by:` `CADRUMO-WINDOWMANAGER`
- `S02` `M` `native/desktop/frontend/src/App.tsx`
- `S02` `A` `native/desktop/frontend/src/components/docking/DockWorkspace.tsx`
- `S02` `A` `native/desktop/frontend/src/components/docking/PaneChrome.tsx`
- `S02` `M` `native/desktop/frontend/src/components/PaneHeader.tsx`
- `S02` `M` `native/desktop/frontend/src/components/agent/AgentHeader.tsx`
- `S02` `M` `native/desktop/frontend/src/components/Rail.tsx`
- `S02` `M` `native/desktop/frontend/src/components/ui/icon.tsx`
- `S02` `M` `native/desktop/frontend/src/styles/tokens.css`
- `S02` `M` `native/desktop/frontend/src/shell/docking.ts`
- `S02` `M` `dev/locales/desktop_interface_keys.py`
- `S02` `M` `dev/locales/desktop_chrome.py`
- `S02` `M` `src/cadrumo/locales/en/common.yml`
- `S02` `M` `src/cadrumo/locales/es/common.yml`
- `S02` `M` `src/cadrumo/locales/ca/common.yml`
- `S02` `M` `src/cadrumo/locales/hu/common.yml`
- `S02` `M` `native/desktop/frontend/tests/scenarios/columns.spec.ts`
- `S02` `M` `native/desktop/frontend/tests/scenarios/keyboard.spec.ts`
- `S02` `M` `native/desktop/frontend/tests/scenarios/scenarios.spec.ts`
- `S02` `M` `native/desktop/frontend/tests/scenarios/ledger-shell.spec.ts`
- `S02` `M` `native/desktop/frontend/tests/scenarios/sede-browser.spec.ts`
- `S02` `verify:` `tsc --noEmit` -> `pass`
- `S02` `verify:` `targeted ESLint docking and migrated header scenarios` -> `pass`
- `S02` `verify:` `playwright docking columns ledger-shell 29 cases` -> `pass`
- `S02` `verify:` `playwright fullscreen session status calendar browser close 7 cases` -> `pass`
- `S02` `verify:` `node --test tests/live/docking.unit.ts` -> `pass`
- `S02` `verify:` `cmake --build --preset debug --target desktop-frontend-chrome` -> `pass`
- `S02` `by:` `CADRUMO-WINDOWMANAGER`
- `S03` `M` `native/desktop/src-tauri/src/shell/window_controls.rs`
- `S03` `M` `native/desktop/src-tauri/src/shell/window_state.rs`
- `S03` `M` `native/desktop/frontend/src/ipc/contract.ts`
- `S03` `M` `native/desktop/frontend/src/components/Titlebar.tsx`
- `S03` `A` `native/desktop/frontend/src/shell/useFullscreen.ts`
- `S03` `M` `native/desktop/frontend/src/dev/scenarioHost.ts`
- `S03` `A` `native/desktop/frontend/tests/scenarios/docking.spec.ts`
- `S03` `M` `native/desktop/frontend/tests/ledger-contract.spec.ts`
- `S03` `verify:` `cmake --build --preset debug --target desktop-host-unit-test with shell::window filter (10 tests)` -> `pass`
- `S03` `verify:` `playwright fullscreen fixture restoration F11 Escape and independent expand/restore` -> `pass`
- `S03` `verify:` `tsc --noEmit` -> `pass`
- `S03` `verify:` `targeted ESLint and Prettier` -> `pass`
- `S03` `verify:` `integrated code review and screenshot inspection` -> `pass`
- `S03` `by:` `CADRUMO-WINDOWMANAGER`
- `S03` `M` `native/desktop/frontend/src/components/docking/DockWorkspace.tsx`
- `S03` `verify:` `playwright docking expanded tab groups (1 focused case)` -> `pass`
- `S03` `verify:` `canonical native_contract operational settings generation` -> `pass`
- `S03` `verify:` `tsc --noEmit after expanded-group correction` -> `pass`
- `S03` `verify:` `npx eslint src/components/docking/DockWorkspace.tsx tests/scenarios/docking.spec.ts (final expanded-tab correction)` -> `pass`
- `S03` `verify:` `npx prettier --check src/components/docking/DockWorkspace.tsx tests/scenarios/docking.spec.ts (final expanded-tab correction)` -> `pass`

## Notes

- `S01` Semantic discovery unavailable: client 0.6.0 / service 0.6.4 mismatch; owning ADR listing and static source discovery used.
- `S02` Shared worktree commit ba32118b52 captured initial S02/S03 implementation during execution; merge 5c8dfd19a4 incorporated unrelated TUI work. This checkpoint records the final single-header correction without rewriting shared history.
- `S02` Full npm check passed TypeScript, ESLint, ledger contract and 34 unit checks; whole-tree Prettier reports pre-existing LedgerPage.tsx formatting. Changed files are formatted.
- `S03` Initial native build was blocked by missing publisher configuration; the existing main-checkout publisher configuration was passed only in the child build environment and the canonical native test target then passed. No dependency locks or synthetic inputs were changed.
- `S03` Final review found expanded-group tab selection retained the old expansion target. Corrected the target and restore workspace presentation for split/float/swap actions. Focused verification initially could not start because concurrent work added a generated operational-settings requirement; canonical `native_contract` regeneration is required.
