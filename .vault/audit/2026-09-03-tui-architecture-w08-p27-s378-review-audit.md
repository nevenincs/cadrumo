---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:7e32dc327024ccc1fe1191de6a0bd14ca8c8f41880959247ad338dbcda59f20c'
related: []
---
# `tui-architecture` audit: `W08.P27.S378 Declarations calendar screen review`

## Scope

Independent review of the live S378 calendar screen, controller, presentation protocols, route integration, tests, locales, and S393 safe projection boundary. The review probed exact scope overlap, evidence observability, known empty/stale/refusal states, Unicode AND search over safe fields, natural callbacks and recovery authority, source/detail truth, semantic focus through filtering and re-entry, eighty-column geometry and scroll ownership, localization, and forbidden dependencies.

## Findings -- final dispositions

### recovery-action-is-an-unlabelled-direct-mutation | high | Closed

Recovery-bearing rows now render an explicit localized create/recover verb in the selected-row detail before activation. The controller rejects any recovery action whose catalogue identity is not `operator.modelo.work.create`, whose catalogue target is not `modelo.work.create`, or whose bindings do not exactly equal the row's natural Modelo/year/period address. Activation routes recovery rows only to the injected recovery handoff; an absent executor renders the existing localized handoff refusal and never falls through to the ordinary entry callback. Highlighting only renders detail. The focused tests prove invalid identity and bindings are rejected, the visible verb is present, the canonical payload is invoked once on Enter, ordinary handoff is not invoked, and the missing-executor path refuses visibly.

### available-source-without-timestamp-is-labelled-never-observed | medium | Closed

Freshness rendering now branches on both availability and timestamp. `NEVER_CAPTURED` alone receives Never observed; `AVAILABLE` without `observed_at` receives localized current/available wording that says the observation time was not recorded; other no-timestamp states receive neutral time-not-recorded wording. The focused screen test constructs the valid `AVAILABLE`/no-time state and proves the rendered detail contains the current/no-time copy and excludes Never observed.

### calendar-ignores-semantic-focus-on-route-entry | medium | Closed

The controller now resolves a namespaced public focus key back to the safe natural row identity. Mount restores the agenda widget and exact semantic row from `TuiScreenContext.focus`. The screen retains a hidden restore anchor while filtering removes the row, does not let the temporary fallback cursor overwrite it, and restores the row when it reappears. Projection replacement resolves by identity rather than position. Tests exercise mount focus, disappearance/re-entry, resize, child-screen return, actual `DataTable` cursor identity, and viewport bounds. A supplemental read-only runtime probe changed the target from rendered row 1 to row 2 by changing its sort key; the cursor followed the semantic identity and remained inside the actual viewport.

## Positive findings

The six scope predicates have explicit tested overlap: Past includes filed and overdue closed windows, while Overdue, Filed, and Upcoming select their distinct application-owned user states. Evidence Unknown is based on AEAT source observability, not the observable `NOT_OBSERVED` value, so known absence remains distinct from inability to know. Unicode NFKD/casefold AND search uses only natural address, localized state labels, and safe dates; protected work, filing, revision, NIF, URL, names, and raw evidence fields are absent.

Rows and callbacks resolve through semantic natural identities rather than cursor positions. Detail copy separates legal, local filing, AEAT submission, justificante, and all three source availability axes. Known empty, stale empty, filtered empty, and unavailable schedule routes are distinct. Eighty-column compositor checks show no horizontal table scroll and one page scroll owner. Four locales contain authored title, status, and detail copy with no key fallback. The package consumes only the injected safe projection and protocols and imports no adapters, CLI, repositories, readers, filesystem or network facilities.

## Final verification

Five narrowly selected remediation tests passed with the integration lane explicitly enabled (`-n 0 -m ""`). They cover recovery catalogue/address validation, visible recovery/refusal behavior, available-without-time copy, route-context focus, hidden-filter restoration, resize, child return, cursor identity, and viewport bounds. The supplemental actual-reorder runtime probe also passed. The prior full-slice Ruff and ty results remain applicable; no production dependency boundary changed in the remediation.

## Final recommendation

CLOSE. All three recorded blockers are remediated and re-proved. No high, medium, or remediation-introduced regression remains open; S378 may close.

