---
tags:
  - '#audit'
  - '#live-iva-compensation-wallet'
date: '2026-07-05'
modified: '2026-07-17'
related:
  - "[[2026-05-19-live-iva-compensation-wallet-adr]]"
  - "[[2026-06-19-iva-compensation-override-cli-adr]]"
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
---

# `live-iva-compensation-wallet` audit: `Sticky decision refresh code review`

## Scope

Reviewed the focused sticky-decision refresh follow-up for the live IVA wallet
authority path. The review covered the accepted wallet ADR requirement that every
run reconcile wallet/local evidence when both are available, the override ADR's
explicit note that general persisted-decision refresh remained a follow-up, the
change to `resolve_iva_compensation_decision_for_calculation`, and the new
regression proving a later seeded 2025 4T carry replaces an earlier 2026 1T
`first_period_zero` replay decision.

## Findings

### sticky-first-period-refresh | low | Narrow refresh matches the accepted wallet authority

The implementation does not introduce a new source kind, resolver convention, or
authority hierarchy. It refreshes only persisted `first_period_zero` decisions,
recomputes the local recurrence path without persisting unless the material replay
basis changes, and then saves the refreshed decision before replay. The new
regression exercises the real Modelo 303 engine: the first calculation records
zero, a later seeded prior-period carry appears, the next calculation blocks as
`filed_history_only`, and the repository now carries the refreshed blocked
decision with the seeded 2025 4T source period.

### residual-live-plan-state | low | Live-wallet plan remains operator-gated

The code follow-up does not close the standing live verification row in the
live-wallet plan. Current status remains 101 of 102 with `W06.P15.S56` open by
its own wording as an opt-in live read-only path and privacy guard. The status
checker also reports historical missing exec records for older checked rows; no
plan checkbox or exec reconciliation was changed in this code-review pass.

### exec-record-reconciliation | low | Historical checked rows now have canonical records

Reviewed the 49 canonical exec records scaffolded for checked rows `S05` through
`S49`, `S61`, `S62`, and `S69`. The records use `vaultspec-core vault add exec`
frontmatter, keep the plan and source tree unchanged, and explicitly scope the
work as traceability repair rather than implementation. `vault plan status`
now reports no `exec-missing` alert for the live-wallet plan; completion remains
101 of 102 because the standing live verification row is still intentionally
open.

### standing-live-verification | medium | S56 is formally deferred as an operator-evidence guard

`W06.P15.S56` is formally deferred, not silently left open. Its blocker is the
standing requirement for fresh operator-owned, opt-in, read-only AEAT evidence
with redacted aggregate diagnostics and no committed private taxpayer values.
The plan row itself says to "add and keep open" this path and later records that
the row "remains open as a standing live-verification path and privacy guard."
Checking the row now would remove the active privacy/evidence guard rather than
complete missing implementation. Follow-up remains the next operator-observed
read-only live verification run or an explicit coordinator decision to retire
the standing guard into a successor campaign.

## Recommendations

Keep this follow-up scoped to `first_period_zero` replay refresh. Do not broaden
taxpayer override refresh or live-wallet recapture semantics without a separate
approved step, because the override ADR explicitly left that broader behavior as
follow-up work. Treat the live-wallet plan as not closed until the operator-gated
standing row and historical exec-record alerts are reconciled under their own
authority.

For the exec-record reconciliation, keep the new records vault-only. Do not infer
new implementation completion from them, and do not close `W06.P15.S56` without
fresh operator-owned live-read evidence or an explicit formal deferral decision.

This audit supplies the formal deferral decision for `W06.P15.S56`. Keep the row
unchecked until either the next operator-observed live run records fresh redacted
aggregate evidence or a successor campaign explicitly owns the standing guard.
Do not treat local recurrence as final authority merely because this standing
guard is deferred.
