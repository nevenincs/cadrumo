---
tags:
  - '#audit'
  - '#cadrumo-windowmanager'
date: '2026-11-02'
modified: '2026-11-02'
body_schema: 'body-v2'
body_hash: 'sha256:422df2a62120e5b71dfd860df4797d36ebbf99f54bbe2fbbd81db8a14ad9b3cc'
related:
  - "[[2026-11-02-cadrumo-windowmanager-plan]]"
---

# `cadrumo-windowmanager` audit: `Integrated docking review`

## Scope

Integrated review of S01-S03: the initial model checkpoint `63bd863c62`, the implementation captured by shared commit `ba32118b52`, and the final single-header correction `ba5bf9b288` with its regression tests. Reviewed layout identity and restoration, stable mounted contents, keyboard and pointer interactions, page-close guards, native fullscreen authority, and saved normal-window geometry. The unrelated TUI merge and CADRUMO-FRONTEND changes remain outside this implementation scope; calendar/profile integration evidence is included where the shared composition was exercised.

After the check-ownership handoff, concurrent frontend hook extraction and asset/installer work began in the shared tree. Those later changes are outside this reviewed checkpoint and were not staged or claimed as verified here.

## Findings

### pane-chrome | medium | Duplicate titles and layout controls resolved

The first integration retained the old pane bars beneath the new docking strips. The user identified the duplication. `components/docking/PaneChrome.tsx` now identifies docked presentation; `PaneHeader.tsx` renders only page-specific tools, and `agent/AgentHeader.tsx` retains conversation actions without the old layout buttons. Session state moves to the tab indicator and description. The tab strip owns title, expand/restore and close. Fullscreen is a separate operation; restoring pane size leaves the native fullscreen state intact. Screenshot inspection and the dedicated single-header and mode-restoration scenarios pass.

### fullscreen-navigation | medium | Hidden-panel shortcut and closing-menu focus races resolved

A console shortcut initially treated a pane concealed by fullscreen as visible and hid it instead of revealing it. Visibility now governs the toggle. The closing docking menu could then recapture focus from the console; the shell retains the focus request until that menu unmounts. The regression verifies both visibility and terminal focus during fullscreen navigation, then checks layout restoration on exit.

### identity-lifetime | low | Validated presentation moves retain one mounted owner

The model removes a source before inserting it into a target group, rejects duplicate or unknown stored identities, bounds recursion and geometry, and keeps closed identities available for reopening. Flat keyed content containers retain the same mounted terminal through all directional splits, tabs and floating. Five model tests and browser retention/rail-drag tests pass. Native controls still refuse non-main windows. Floating panes remain inside the main window.

### verification | low | Scoped review passes with a known unrelated formatting failure

PASS for the scoped implementation. The latest browser evidence is 29 passing docking/column/Ledger scenarios in run `20261102T145120Z-51904`, followed by seven passing fullscreen/status/calendar/browser-close cases. Earlier integrated coverage passed the entire keyboard suite and all six calendar-coverage cases plus the profile-views regression; targeted reruns resolved the two initial docking expectations. Final TypeScript, targeted ESLint, targeted Prettier, five model tests and locale declaration lint pass. The canonical CMake desktop-host-unit-test run filtered to `shell::window` compiled successfully and passed ten native tests. The canonical chrome generator succeeded with all four locales. Native tests establish compilation and window-control contracts; no packaged OS-interaction smoke test is claimed.

The full frontend check passed TypeScript, ESLint, ledger-contract validation and all 34 unit checks, then reported pre-existing formatting in `src/components/ledger/LedgerPage.tsx`. That unrelated file was not reformatted. The MCP vault health-check timed out, so scoped owning CLI checks were used instead.

### expanded-group-target | medium | Selected tabs now replace the expansion target

The final interaction review found that an expanded group could retain its previous pane when another tab was selected. The docking strip now updates the expansion target on selection. Split, float and swap operations first restore workspace presentation so their result is visible. A focused browser regression passed for tab switching in both directions, then splitting and floating from the expanded state. TypeScript passed on the shared tree after this correction. Concurrent work had added a generated operational-settings dependency; the canonical `native_contract` target generated it before the browser rerun, with no synthetic inputs or dependency-lock changes.

## Recommendations

No unresolved high or critical findings. Preserve the distinction between workspace expansion and native fullscreen and keep page-specific actions separate from pane layout controls. Separate native floating windows would require a new authority/lifecycle decision. CADRUMO-FRONTEND received verification ownership back; the canonical dev server remains running for user inspection.
