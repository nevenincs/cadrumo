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

2026-07-02 refresh: `uv run --no-sync vaultspec-core vault plan status
2026-06-26-binding-resolver-contract-unification-plan --json` reports 12 of 21
steps complete, `next_open_step` = `P03.S10`, and `exec_missing_ids` = `[]`.

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
steps are formally deferred to the existing #36 shape-C adjudication follow-up, which
must either amend S13/S19/S14 to the canonical mesh-preview retirement shape or replace
them with a successor plan before any checkbox or exec record is claimed.

### hub-file-wip-blocks-enrollment-work | medium | `_calculation_actions.py` is dirty and single-owner

The remaining enrollment/final-gate surface includes `src/aeat/application/modelo/_calculation_actions.py`,
which has non-authored WIP in the shared worktree. The dispatch brief treats that file
as single-owner. This pass did not touch it. P05.S18 remains open until P03 is resolved
and the gate surface is peer-clean.

## Fresh-Context Honesty Review

Reviewed the campaign as newly inherited, using the current plan status, the ADR
execution refinement, the shape-C research, the live invoice resolver evidence, the
exec-record inventory, and the shared-worktree WIP checks as the authority. Findings:

### close-counterpart-foreign-assets | medium | S10/S11/S12/S20/S21 are intentionally not phase-2.2 work

The ADR execution refinement already scopes counterpart 347/349 and foreign-assets 720
out to task #36. Current code confirms the rationale: M349 is live through
`InvoiceCatalogueSourceResolver`, M347 has no calculate modelling to feed a mesh
resolver, and M720 remains an explicit deferred source rather than a silent blank. These
rows must stay unchecked until #36 decides per modelo whether to retire, promote, or
re-ratify the shape-C surface.

### close-retenciones-cli | medium | S13/S19/S14 need #36 shape-C adjudication before implementation

The later shape-C research recommends retiring the second `aggregate_per_modelo`
rollup and deriving CLI preview from canonical mesh outputs, while the old plan rows
still describe collapsing retenciones inside the existing service. Implementing those
rows as written would preserve a second aggregation mechanism. The formal follow-up is
#36: amend or replace the retenciones/CLI projection rows with the canonical
mesh-preview retirement shape, then execute with real parity gates.

### close-final-gate | medium | S18 cannot run until the deferred P03 shape is resolved

`P05.S18` asks for the full unified resolver-contract gate after P03 is complete. With
P03 formally deferred to #36 and `_calculation_actions.py` carrying non-authored
single-owner WIP, running or checking S18 now would overclaim. The named follow-up is
#36 completion plus a peer-clean final-gate window for `P05.S18`.

## Closure Decision

For Wave 1 D9 purposes, this campaign's remaining tail is honestly drained: every open
row is formally deferred to #36 or to the peer-clean final-gate window that follows
#36. The vault plan remains open by design; no missing exec alert remains and no new
resolver convention was introduced under the freeze.

## Recommendations

Keep the deferred counterpart/foreign-assets steps unchecked unless the coordinator
updates the existing plan to match the #36 research. Re-open the retenciones/CLI
projection work only after #36 makes the intended shape explicit, then run P05.S18.
Do not lift the bindings freeze from this campaign: `vault plan status` still reports
open steps, though the missing-exec alert is resolved.
