---
tags:
  - '#audit'
  - '#desktop-navigation-register'
date: '2026-10-24'
modified: '2026-10-25'
body_schema: 'body-v2'
body_hash: 'sha256:e4742844acee5d1d98ee1c47a4335484a9caf4da2101850f6c9e8b9b823d2b0a'
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

### re-review | info | the fixes pass; close-guard, tui-select-drop, suppression and dead-reference are resolved

Re-review of 60919dd504, 4b72c60404, acf769b08f, af1a2ae3b3, 28a0e4e726, 7753bd61c8 and fa21f00c36: verdict pass with findings, no critical or high. A dialog no longer holds the close, a close during a waiting question is left unanswered so the host's second close closes, and normal navigation still stands down for a dialog; the six `window-close.spec.ts` scenarios drive the real navigator and fail three of six on the old guard. All four catalogues parse from af1a2ae3b3 on, and the only key-level change across acf769b08f^..af1a2ae3b3 is the added `tui.ledger.overview.selection_dropped`; acf769b08f alone does not parse. `resolve_view` now has a production consumer in the MCP link check. The palette half of register-duplication is fixed; the host test half is a parked patch that cannot compile while another session's uncommitted `native/application` Cargo change breaks `--locked`.

### retired-reuse | medium | an id removed from `retired` can be declared again without a test failing

The shipped-id baseline (`src/cadrumo_client/contracts/tests/navigation_shipped_views.json`) records shipped ids but not which are retired, so un-retiring and re-declaring passes (`test_navigation_register.py:230-245`). Fix in progress: a retired list in the baseline that only grows.

### adr-wording | medium | the amendment's guard bullet still let a dialog hold the window's close

Reconciled in the amendment the same day: `modal` stands down every navigation except the close, and the close sentence states that a dialog never holds it.

### tui-select-drop-area | low | the dropped-selection notice can name the wrong area and does not follow a language switch

`routes.py:217-220` adds it for any refused area, including one chosen by an action id; `overview.py:95` writes it into an unlocalized widget. Fix in progress, with the whole-ledger-unavailable placeholder also mentioning the dropped selection and the fixture literal at `workspace_fixtures.py:127` using the constant.

### locale-process | low | acf769b08f inserted a key by line offset and broke all four catalogues at that commit

af1a2ae3b3 repaired it; a bisect landing on acf769b08f fails at startup. Keys go through the `dev.locales` set-batch workflow.

### window-controls-spec | info | `tests/window-controls.spec.ts:136` expects `close` from the titlebar button

The button has sent `close_now` through the close guard since fa2ece7b7f, before this plan; not caused or fixed here. The `product` Playwright project has not run since the fixes because its build writes the shared `dist/` from a working tree holding other sessions' unfinished frontend edits.

## Recommendations

- close-guard: decide a close before the modal rule and never refuse it for a dialog; leave a close that arrives while a prompt is pending unanswered so the host's second-close rule applies; add scenarios for a close over the sign-in dialog and two closes over a leave prompt. Fixed under reopened `S10`.
- tui-select-drop: announce the dropped selection on the overview when the landing was chosen for a transaction focus; test through the real ledger screen factory. In scope of `S07`.
- retired-append-only: add a growing baseline of every id ever shipped; assert each is declared or retired and that `retired` only grows. In scope of `S06`.
- register-duplication: derive the palette icon list from the register's `ledger` children and assert the host's TUI admission against the projection. In scope of `S12` and `S09`.
- link-producers-literal, suppression: use the one constant; drop the marker or change the import so the rule does not fire.
- dead-reference: give `resolve_view` a production consumer where it adds value (the MCP `views` link check reporting where a valid link opens), or remove it and keep the resolve vectors as the TypeScript oracle.
- Not decided here: whether the window should honour `select` on `ledger` itself by opening the movements grid; today such a link opens in the TUI with a notice, as the resolution order says.
