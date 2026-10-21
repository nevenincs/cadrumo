---
tags:
  - '#exec'
  - '#desktop-titlebar'
date: '2026-10-09'
modified: '2026-10-09'
body_schema: 'body-v2'
body_hash: 'sha256:42c45cf40f6a2dda3d997e8b8f0f1b710c6e2af347e6360d2da97197f51a941b'
related:
  - "[[2026-10-09-desktop-titlebar-plan]]"
---

# `desktop-titlebar` ledger

## Changes

- `S01` `M` `dev/locales/desktop_chrome.py`
- `S01` `M` `native/desktop/frontend/src/App.tsx`
- `S01` `A` `native/desktop/frontend/src/components/Titlebar.tsx`
- `S01` `A` `native/desktop/frontend/src/components/AccountMenu.tsx`
- `S01` `M` `native/desktop/frontend/src/components/Settings.tsx`
- `S01` `M` `native/desktop/frontend/src/components/Settings.stories.tsx`
- `S01` `M` `native/desktop/frontend/src/components/SignIn.tsx`
- `S01` `M` `native/desktop/frontend/src/components/SignIn.stories.tsx`
- `S01` `M` `native/desktop/frontend/src/components/accountWords.ts`
- `S01` `M` `native/desktop/frontend/src/components/ui/icon.tsx`
- `S01` `M` `native/desktop/frontend/src/ipc/contract.ts`
- `S01` `M` `native/desktop/frontend/src/shell/host.ts`
- `S01` `M` `native/desktop/frontend/src/shell/signIn.ts`
- `S01` `M` `native/desktop/frontend/src/shell/tauriHost.ts`
- `S01` `M` `native/desktop/frontend/src/shell/useWindowPresentation.ts`
- `S01` `M` `native/desktop/frontend/src/styles/shell.css`
- `S01` `M` `native/desktop/frontend/src/styles/titlebar.css`
- `S01` `M` `native/desktop/frontend/tests/desktop.spec.ts`
- `S01` `M` `native/desktop/frontend/tests/scenarios/accessibility.spec.ts`
- `S01` `M` `native/desktop/frontend/tests/scenarios/profiles.spec.ts`
- `S01` `M` `native/desktop/frontend/tests/scenarios/scenarios.spec.ts`
- `S01` `A` `native/desktop/frontend/tests/scenarios/titlebar-account.spec.ts`
- `S01` `A` `native/desktop/frontend/tests/window-controls.spec.ts`
- `S01` `M` `native/desktop/src-tauri/src/app.rs`
- `S01` `M` `native/desktop/src-tauri/src/shell/mod.rs`
- `S01` `A` `native/desktop/src-tauri/src/shell/window_controls.rs`
- `S01` `M` `native/desktop/src-tauri/tauri.conf.json.in`
- `S01` `M` `src/cadrumo/locales/en/common.yml`
- `S01` `M` `src/cadrumo/locales/es/common.yml`
- `S01` `M` `src/cadrumo/locales/ca/common.yml`
- `S01` `M` `src/cadrumo/locales/hu/common.yml`
- `S01` `verify:` `npm run check` -> `pass`
- `S01` `verify:` `npm run storybook:build` -> `pass`
- `S01` `verify:` `playwright full scenarios (297 pass, 2 retired selectors)` -> `fail`
- `S01` `verify:` `playwright focused corrected calendar/messages selectors (2 tests)` -> `pass`
- `S01` `verify:` `playwright full product (98 tests)` -> `pass`
- `S01` `verify:` `run-backend.ps1 window_controls (2 tests)` -> `pass`
- `S01` `verify:` `run-backend.ps1 every_registered_command_requires_the_shell_token (1 test)` -> `pass`
- `S01` `verify:` `run-backend.ps1 -Mode Clippy` -> `pass`
- `S01` `verify:` `rustfmt --check window_controls/mod/app` -> `pass`
- `S01` `verify:` `pytest dev/locales/tests/test_desktop_chrome.py (16 tests)` -> `pass`
- `S01` `verify:` `ruff check dev/locales/desktop_chrome.py` -> `pass`
- `S01` `verify:` `node native/desktop/scripts/tauri.mjs build (Windows Debug)` -> `pass`
- `S01` `verify:` `git diff --check` -> `pass`
- `S01` `by:` `Codex`
- `S01` `verify:` `playwright final header accessibility/geometry/transport (8 tests)` -> `pass`
- `S01` `A` `native/desktop/frontend/src/components/account/AccountRefusal.tsx`
- `S01` `verify:` `playwright final shared renderer/header/account (9 tests)` -> `pass`

## Notes

- `S01` Session 0 prohibits interactive GUI verification here; Windows OS interactions and Linux native execution remain unverified. Existing macOS application refusal is preserved.
- `S01` Concurrent sign-in observation and development-port work in shared files is excluded from this step's commit. Dev entry retirement/shared titlebar token placement landed in 19c8049413 during execution; existing just-dev display continues to serve the real App.
- `S01` The final shared presentation refactor extracts AccountRefusal from SignIn; header and credential form use that same renderer. Included as a required header dependency, with no authentication observation changes.
