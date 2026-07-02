---
tags:
  - '#audit'
  - '#binding-resolver-contract-unification'
date: '2026-07-02'
modified: '2026-07-02'
related:
  - "[[2026-06-26-binding-resolver-contract-unification-plan]]"
---

# `binding-resolver-contract-unification` audit: `Wave 1 D9 close-blocker audit`

## Scope

Wave 1 D9 close-blocker pass over the resolver-contract plan status on 2026-07-02.
The pass reconciled the plan alert for S04, read the ADR execution refinement and
shape-C research, then checked the remaining P03/P05 targets against live code and
the shared-worktree WIP boundary. This audit is not a closure honesty review because
the campaign is not structurally complete.

## Findings

### exec-alert-reconciled | low | S04 now has a dedicated exec record

Plan status reported `exec-missing: S04`. The code change landed earlier in commit
`52edec4b1` together with S02, and the S02 record already described both actions.
This pass added a dedicated S04 exec record, so plan status no longer reports missing
execution records.

### counterpart-foreign-asset-fold-deferred | medium | S10, S11, S12, S20, and S21 are scoped out by the ADR refinement

The ADR execution refinement and the shape-C research classify counterpart 347/349
and foreign-assets 720 as non-mechanical follow-up work. Implementing S10/S11/S12
now would add live resolver behavior for counterpart/foreign-asset sources while the
program ADR freezes new resolver conventions; it also contradicts the research result
that M349 is already live through invoice resolution, M347 has no calculate modelling,
and M720 is already advisory-deferred. These steps remain unchecked and formally
deferred to the existing #36 follow-up classification path.

### retenciones-shape-c-tail-needs-adjudication | medium | S13, S19, and S14 are stale against the latest shape-C research

The still-open retenciones collapse and CLI projection steps are not safe to land as
written. The latest research recommends retiring the shape-C rollup and deriving the
CLI preview from canonical mesh outputs, while the plan still describes collapsing
retenciones inside the existing per-modelo service. Landing the older step text would
risk preserving the second aggregation mechanism the research says to retire. These
steps are deferred pending coordinator adjudication of the exact execution shape.

### hub-file-wip-blocks-enrollment-work | medium | `_calculation_actions.py` is dirty and single-owner

The remaining enrollment/final-gate surface includes `src/aeat/application/modelo/_calculation_actions.py`,
which has non-authored WIP in the shared worktree. The dispatch brief treats that file
as single-owner. This pass did not touch it. P05.S18 remains open until P03 is resolved
and the gate surface is peer-clean.

## Recommendations

Keep the deferred counterpart/foreign-assets steps unchecked unless the coordinator
updates the existing plan to match the #36 research. Re-open the retenciones/CLI
projection work only after the intended shape is made explicit, then run P05.S18.
Do not lift the bindings freeze from this campaign: `vault plan status` still reports
open steps, though the missing-exec alert is resolved.
