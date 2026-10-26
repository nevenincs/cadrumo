---
tags:
  - '#audit'
  - '#desktop-titlebar'
date: '2026-10-09'
modified: '2026-10-09'
body_schema: 'body-v2'
body_hash: 'sha256:5110c623346648a78ec00c3e123b9db744676f94d2a1870e9b1128ebf43c1630'
related:
  - "[[2026-10-09-desktop-titlebar-plan]]"
  - "[[2026-10-09-desktop-titlebar-adr]]"
---

# `desktop-titlebar` audit: Tauri header and account relocation

## Scope

Integrated review of S01 against the accepted desktop-titlebar, desktop-shell, desktop-design-system amendment and application-sign-in decisions. Diff base is commit 19c8049413 plus this step's working-tree changes. Concurrent runtime lifecycle, development-server and sign-in observation work is excluded from the step's commit. Review traces product composition, Settings retirement, account controller and credential form, native dispatch and cleanup, shared tokens, localization and browser fixtures.

Native window actions remain a closed set of supported Tauri Rust methods. The app dispatcher checks the per-launch token, and all actions and subscriptions refuse another window label. No core-window JavaScript capability or documentation bridge command is granted. Native close raises CloseRequested and preserves the established shutdown refusal path. Initial state and resize/focus publications drive maximize/restore; stale unsubscription cannot remove a new listener. Browser controls remain disabled.

The old Settings Account export and account prop, stories and session catalogue key are retired. The header dropdown uses the existing account controller; sign out is offered once there. Coherent signed-out profile selection and existing credential/create dialogs retain canonical authority. Menu dismissal settles seen refusals; destination actions suppress the menu's focus restoration. The account popover contains a separately labelled action menu, with feedback outside its menu semantics. Shared geometry remains token-owned and the brand retains the approved text-box alignment.

## Findings

### native-platform-coverage | low | Interactive native acceptance requires an available desktop

The Windows executable builds and focused Rust tests establish command authentication, action grammar, main-window refusal and subscription cleanup. The browser transport test proves adapter routing and native-state presentation, not real OS window behavior. This host executes in Session 0, where the existing project rules prohibit a GUI bridge; interactive minimize, restore, drag, snap, resize and shutdown were not exercised. Linux native execution is unavailable. macOS application admission remains refused by existing code. These are explicitly bounded acceptance limits, not simulated native evidence.

## Recommendations

Review verdict: PASS for the implementation and verification available under the approved plan's environment condition. No open high or critical findings. Before platform release, run the existing packaged desktop on an interactive Windows desktop and an admitted Linux desktop, checking drag/double-click, OS resize/snap, minimize/restore state, keyboard navigation and normal close cleanup.

Verification against the final working tree: `npm run check` passes type checking, lint, rule tests and formatting; `npm run storybook:build` passes. Full scenarios run has 297 passing tests and two stale Settings selector failures; both selectors were repaired and their focused rerun passes. All 98 product tests pass, including native window transport, CSP and documentation isolation. Earlier header/account focused runs are superseded where changed. `pytest dev/locales/tests/test_desktop_chrome.py -q` passes 16 tests; `ruff check dev/locales/desktop_chrome.py`, Rust formatting and clippy pass. Focused window_controls tests pass two tests and every_registered_command_requires_the_shell_token passes one. Native Windows Debug build passes. Browser result artifacts are in `build/titlebar-full-scenarios-results`, `build/titlebar-final-targeted-results` and `build/titlebar-product-results`; native artifacts and test snapshots remain CMake-owned.

Final review follow-up: the compact header retains its application heading name when visual lettering is hidden. The final focused header geometry, native transport and shell/account accessibility run passes eight tests, followed by a fresh passing `npm run check` and Windows Debug build. Results are in `build/titlebar-final-accessibility-results`. The action menu is omitted semantically when no actions are available, preserving unknown/checking state accessibility.

Final shared-renderer integration: `components/account/AccountRefusal.tsx` now owns the renderer used by both the credential form and account popover. This presentation extraction and reuse of Logo-owned mark geometry passed a fresh frontend check and nine focused Settings-retirement, profile flow, compact alignment and account accessibility tests (`build/titlebar-shared-renderer-results`). Review remains PASS; no authentication observation work is included.
