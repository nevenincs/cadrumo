---
tags:
  - '#audit'
  - '#desktop-navigation-register'
date: '2026-10-24'
modified: '2026-10-24'
body_schema: 'body-v2'
body_hash: 'sha256:64d8dbb0c0f74a4d47ad8941f72614aacae48f9fcfbab13c53ffa40b74d94e65'
related:
  - "[[2026-10-24-desktop-navigation-register-plan]]"
---

# `desktop-navigation-register` audit: `Desktop navigation register plan-close review`

## Scope

Plan-close integrated review of `2026-10-24-desktop-navigation-register-plan` Steps `S06` to `S12` against the 2026-10-24 amendments of `2026-10-04-desktop-shell-adr` and `2026-08-11-tui-architecture-adr`. Commits reviewed as one change: 0e0288197a, de1e6116ed, 7ba285bd05, f58e0a984f, e7301548b6, 70ae70915f, 9b1dfd3c5d, 53098ff2ca, c1e18a2fba, b780f0120e, 94a1357115, 42298ef117, 6e83e8bb24. Other sessions' interleaved commits and uncommitted edits were excluded. `git diff --stat 606c8bdef5 70ae70915f` holds only navigation files, so the stale-index commit e7301548b6 lost no other session's work. Verdict of the first pass: fail, on one high finding; `S10` reopened.

## Findings

### close-guard | high | an open dialog or pending navigation prompt keeps the system close from ever closing the window

`native/desktop/frontend/src/shell/navigation/guards.ts:95` checks `modal` before the close kind, and `useNavigator.ts:157` and `:167` answer at once through `stay`, which `App.tsx:358` maps to `keep_open`. The host `CloseGuard` (`native/desktop/src-tauri/src/shell/window_controls.rs:38`) lets a second close through only while the page has not answered, and `keep_open` resets it, so every later close is asked and refused again. With the sign-in dialog open at launch, Alt+F4 never closes. The amendment keeps the titlebar rule that a busy owner is asked and a second close still closes. No scenario covered a close over a dialog or a pending prompt.

### tui-select-drop | medium | a TUI ledger link with `select` can land on the overview without saying the selection was dropped

`src/cadrumo/entrypoints/tui/ledger/routes.py:219` demotes the landing to the overview when the entries area is refused, and the `selection_absent` notice is raised only in `LedgerEntriesScreen.on_mount` (`entries.py:143-147`), which this path never runs. The amendment requires a notice whenever a parameter is dropped.

### retired-append-only | medium | the append-only rule for retired ids is not enforced by a test

`src/cadrumo_client/contracts/tests/test_navigation_register.py` refuses a re-declared retired id, but deleting an element without retiring it, or removing an entry from `retired`, is caught only by a hand-pinned set (`:179`) that the same change can edit.

### register-duplication | medium | two hand-written lists repeat register ids

`native/desktop/frontend/src/App.tsx:1795-1801` lists the six `ledger/*` ids for palette icons, and `native/desktop/src-tauri/src/shell/presentation.rs:178-196` lists the eleven TUI ids and pins the count. Both contradict "adding an element is one register entry plus each surface's mapping".

### link-producers-literal | low | the TUI transaction focus key is spelled as a literal beside its constant

`presentation.py:25` defines `LEDGER_TRANSACTION_FOCUS`; `routes.py:215` and `entries.py:143` (and `controller.py:340,357,472`) repeat the string.

### suppression | low | a new `# nosemgrep` marker

`src/cadrumo_client/contracts/navigation.py:28` adds `# nosemgrep` on the `importlib.resources` import; `cadrumo_runtime/adapters/linux_gnome_lock.py:20` uses the same import without one. The project forbids new suppressions.

### dead-reference | low | `resolve_view` has no production consumer

`resolve_view` and its outcome types in `navigation.py` are reached only by tests; by the project's usage rule own-test use does not count. `admitsTuiView` (`register.ts:101`) is reached by the frontend dev scenario host, which counts as development use.

### panel-badge | info | `panel.spec.ts:5` fails independently of this plan

The log-error badge depends on `HostRecordList.onErrors`; 09122b11bd, another session's commit before this plan, moved reporting to a timer whose StrictMode replay cleanup leaves `pending.current` set (`HostRecordList.tsx:41,49`). None of the reviewed commits touches it. The rail-order failure at `scenarios.spec.ts:2137` follows the Declarations rail item from e2f4030f14, outside this plan.

## Recommendations

- close-guard: decide a close before the modal rule and never refuse it for a dialog; leave a close that arrives while a prompt is pending unanswered so the host's second-close rule applies; add scenarios for a close over the sign-in dialog and two closes over a leave prompt. Fixed under reopened `S10`.
- tui-select-drop: announce the dropped selection on the overview when the landing was chosen for a transaction focus; test through the real ledger screen factory. In scope of `S07`.
- retired-append-only: add a growing baseline of every id ever shipped; assert each is declared or retired and that `retired` only grows. In scope of `S06`.
- register-duplication: derive the palette icon list from the register's `ledger` children and assert the host's TUI admission against the projection. In scope of `S12` and `S09`.
- link-producers-literal, suppression: use the one constant; drop the marker or change the import so the rule does not fire.
- dead-reference: give `resolve_view` a production consumer where it adds value (the MCP `views` link check reporting where a valid link opens), or remove it and keep the resolve vectors as the TypeScript oracle.
- Not decided here: whether the window should honour `select` on `ledger` itself by opening the movements grid; today such a link opens in the TUI with a notice, as the resolution order says.
