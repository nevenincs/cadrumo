---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:379a299f69a3757585746dc0f9dd773ee26a52017eccdf94dc027721512cf0ab'
related: []
---
# `tui-architecture` audit: `W08.P27.S378 Declarations calendar screen review`

## Scope

Independent review of the live S378 calendar screen, controller, presentation protocols, route integration, tests, locales, and S393 safe projection boundary. The review probed exact scope overlap, evidence observability, known empty/stale/refusal states, Unicode AND search over safe fields, natural callbacks and recovery authority, source/detail truth, semantic focus through filtering and re-entry, eighty-column geometry and scroll ownership, localization, and forbidden dependencies.

Final re-review includes the runtime locale remediation in `d97db2dd38`.

## Findings

### recovery-action-is-an-unlabelled-direct-mutation | high | Resolved: recovery requires explicit local confirmation before the host handoff

A recovery-row selection opens a confirmation modal and retains one pending typed action plus natural-address row. The callback clears pending state before proceeding, so the host handoff runs only after explicit approval and cannot repeat from the same confirmation. The focused tests prove no call on row highlight or first Enter, one exact typed call after confirm, absent-handoff refusal, Escape cancellation without dismissing the calendar, and sanitized failure display.

### recovery-failure-copy-is-not-localized | medium | Resolved in `d97db2dd38`

Recovery confirmation, cancellation, and generic failure copy now resolve through authored `tui.declarations.calendar.recovery` keys in every shipped locale. The locale-parametrized confirmation lifecycle test asserts the localized modal controls and failure result rather than pinning English prose. Exact-symbol confirmation finds no remaining hard-coded recovery operator strings in the calendar screen.

### available-source-without-timestamp-is-labelled-never-observed | medium | Resolved in `b7b61b60c9`

Source detail now reserves never-observed copy for never-captured authority and distinguishes an available source whose observation time was not retained. The added available-without-timestamp rendering test covers the valid cross-product and prevents the former contradiction.

### calendar-ignores-semantic-focus-on-route-entry | medium | Resolved in `b7b61b60c9`

The controller derives a safe calendar focus key from the natural address, and the screen restores it through filtering, row reordering, projection replacement, resize, and child return. The focused integration test proves exact row identity and agenda focus rather than a cursor position.

## Positive findings

Agenda predicates remain application-derived: Past, Upcoming, Overdue, Filed, and Evidence Unknown retain their distinct source-axis meanings. Unicode search remains limited to safe natural address, dates, and localized state labels. Detail retains independent legal, local filing, AEAT submission, justificante, and source availability axes. The calendar stays host-neutral and projection-only, uses no I/O, adapter, CLI, persistence, or network authority, and has one scroll owner at the supported width.

## Verification

The root re-ran the focused calendar suite with 18 passing tests. Independent re-review confirms Ruff and ty pass for the calendar/declarations slice and basedpyright reports zero errors, warnings, and notes for the calendar and focused test surface.

## Recommendation

Approve S378. Preserve the all-locale recovery confirmation and failure assertions when extending calendar lifecycle actions.
