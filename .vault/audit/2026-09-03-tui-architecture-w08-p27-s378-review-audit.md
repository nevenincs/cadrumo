---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:0458f7fd0b80bf4b611d1e0ec9c5f7edd69ee1d6be9914948541a0ec209297ad'
related: []
---
# `tui-architecture` audit: `W08.P27.S378 Declarations calendar screen review`

## Scope

Independent review of the live S378 calendar screen, controller, presentation protocols, route integration, tests, locales, and S393 safe projection boundary. The review probed exact scope overlap, evidence observability, known empty/stale/refusal states, Unicode AND search over safe fields, natural callbacks and recovery authority, source/detail truth, semantic focus through filtering and re-entry, eighty-column geometry and scroll ownership, localization, and forbidden dependencies.

## Findings

### recovery-action-is-an-unlabelled-direct-mutation | high | Open: Enter can create work without a visible recovery affordance

A row carrying `recovery_action` looks the same as an ordinary calendar row: neither the agenda nor detail copy says that a recovery action exists, names its application-owned meaning, or indicates that activation differs. `on_data_table_row_selected` nevertheless gives recovery precedence and immediately calls `recovery_handoff(action, row)`. The protocol explicitly describes that callback as an executor that submits the pre-admitted recovery action; the canonical action is `operator.modelo.work.create`. Thus the same Enter gesture either navigates or initiates creation based on hidden state.

The tests construct no recovery-bearing row and never exercise `calendar_recovery_handoff`, so action identity, exact bindings, single invocation, refusal, confirmation, and error/lifecycle behavior are unproved. Render an explicit localized recovery affordance derived from the application declaration, separate row inspection from action activation, and require a deliberate confirmation before invoking a mutating executor. Add a canonical S393-projected recovery row and prove exact action/bindings, no invocation on highlight/detail, one invocation after confirmation, and visible refusal when the executor is absent.

### available-source-without-timestamp-is-labelled-never-observed | medium | Open: valid source state renders contradictory freshness

S393 and the inherited `HomeZoneState` contract allow `AVAILABLE` with `observed_at=None`; this can represent current in-memory authority without a retained observation timestamp. `_render_detail` maps every missing timestamp, regardless of availability, to the localized `never_observed` copy. A valid source can therefore render as both Available and Never observed. Reserve Never observed for `NEVER_CAPTURED`; use distinct localized current/no-timestamp wording for available, locked, or unavailable sources whose contract permits no timestamp. Add the valid cross-product to detail-copy tests.

### calendar-ignores-semantic-focus-on-route-entry | medium | Open: route re-entry always starts at search

The controller retains `TuiScreenContextV1`, but the calendar never reads `context.focus`. `on_mount` always focuses the search box and `_refresh` defaults the agenda cursor to the first row. Its semantic preservation test covers only filtering while the selected row remains visible; it does not mount with a calendar natural-address restore token, filter a selected row out and back in, reorder rows, or resize a running compositor. Implement and test a stable calendar semantic focus identity based on the safe natural address, restoring both the exact agenda row and table focus on route re-entry. Preserve that identity through filter disappearance/reappearance and presentation reorder.

## Positive findings

The six scope predicates have explicit tested overlap: Past includes filed and overdue closed windows, while Overdue, Filed, and Upcoming select their distinct application-owned user states. Evidence Unknown is based on AEAT source observability, not the observable `NOT_OBSERVED` value, so known absence remains distinct from inability to know. Unicode NFKD/casefold AND search uses only natural address, localized state labels, and safe dates; protected work, filing, revision, NIF, URL, names, and raw evidence fields are absent.

Rows and callbacks resolve through semantic natural identities rather than cursor positions. Detail copy separates legal, local filing, AEAT submission, justificante, and all three source availability axes. Known empty, stale empty, filtered empty, and unavailable schedule routes are distinct. Eighty-column compositor checks show no horizontal table scroll and one page scroll owner. Four locales contain authored title, status, and detail copy with no key fallback. The package consumes only the injected safe projection and protocols and imports no adapters, CLI, repositories, readers, filesystem or network facilities.

## Verification

All 9 focused calendar tests passed. Ruff passed for the calendar slice. ty passed for the Declarations package. The green suite does not discharge the findings because it has no recovery action, every available source fixture supplies a timestamp, and it never supplies route-entry focus or removes the selected row during filtering.

## Recommendation

NO-CLOSE. Remediate the high hidden mutation and both medium truth/focus defects before marking S378 complete.
