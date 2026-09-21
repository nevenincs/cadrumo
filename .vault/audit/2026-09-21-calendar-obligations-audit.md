---
tags:
  - '#audit'
  - '#calendar-obligations'
date: '2026-09-21'
modified: '2026-09-21'
body_schema: 'body-v2'
body_hash: 'sha256:618b7e406252e3db8fcd2cb98bd03bd4e8dc01d36324760ee29a1a9ecd67bb1c'
related:
  - "[[2026-09-21-calendar-obligations-plan]]"
---
# `calendar-obligations` audit: phase reviews

## Scope

Reviewed P01.S01 through P01.S03 as one effective-date and lifecycle workflow against CALENDAR-01 CA2, CA3 and CA4 and the accepted calendar semantics decisions. Evidence comprised the Step commits, focused tests and the current integrated source. Later passes reviewed P02 evidence/recovery behavior and the completed P03 CLI/TUI/acceptance workflow.

## Findings

### inactive-legal-entity | high | Activity cessation can still erase corporate obligations without extinction evidence

`src/cadrumo/domain/deadlines/engine.py:93` now compares obligations with calendar spans to their tax periods, correctly retaining final-quarter and annual residual obligations. However, `src/cadrumo/domain/deadlines/models.py:632` carries only `activity_end_date`; it has no legal-entity extinction fact. Applying that date as a universal post-baja filter can suppress later corporate obligations for an inactive but legally unextinguished entity. The implementation therefore does not yet satisfy CA4's inactive-entity case and the P01 review result is REVISION REQUIRED.

### phase-p01-rereview | low | Inactive legal entities no longer lose obligations through activity cessation

The reopened P01.S03 resolves legal-entity identity through the pinned authority and prevents `activity_end_date` from impersonating extinction. Natural-person and attribution lifecycle filtering remains period-based. The focused engine and lifecycle suite passes, so the repeated P01 review result is PASS.

### phase-p02 | low | Evidence and recovery remain fail-closed and non-assessive

P02 preserves local filing, official AEAT evidence and receipt verification as separate axes. Notification rows remain additive message observations even when their prose resembles a filing, and replay deduplicates without creating filing coordinates or evidence. The shared declarations projection carries the registry-derived Article 27 band only as an `unassessed` conditional rate preview; it has no amount or liability field. Focused application tests pass and the phase review result is PASS.

### plan-close | low | CLI and TUI preserve one explicit calendar meaning offline

CLI and TUI expose the same evaluation date, original and effective closes, payment cutoff, overdue age, local filing state, AEAT evidence state and receipt certainty from shared application contracts. The acceptance fixture uses independently seeded immutable stores for each frontend and compares their typed meanings. The bounded integrated run passed 97 application/CLI/acceptance tests and 18 TUI tests. No network or notification-content path was invoked. Final review result: PASS.

## Recommendations

Reopen P01.S03. Preserve the existing activity-period behavior for natural persons and attribution entities, but do not treat a legal entity's activity cessation as proof of extinction. Surface the missing extinction distinction explicitly and add a focused legal-entity regression before closing the Step and repeating this phase review.

The high finding is resolved by the reopened Step. Continue to P02 without introducing an extinction schema; a future explicit extinction capability would require its own grounded contract.

P02 requires no revision. Persistent notification-to-filing association remains a deferred capability and is not a dependency of the negative unlinked-notification contract.

The completed plan requires no further revision. Live AEAT reconciliation, authentication, notification content, acknowledgement, response and filing submission remain NOT EXERCISED.
