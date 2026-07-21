---
tags:
  - '#audit'
  - '#binding-resolver-contract-unification'
date: '2026-07-02'
modified: '2026-07-17'
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

## 2026-07-02 D9 Follow-Up Refresh

The D9 follow-up execution moved the earlier #36 counterpart/foreign-assets
classification forward. `P03.S10` and `P03.S11` are no longer deferred: they have
landed exec records and plan checks for the counterpart and foreign-assets resolver
classes. A targeted `P03.S21` pass then added M349 correctness evidence in
`src/aeat/application/aggregation/tests/test_per_modelo_service.py`.

The M349 fixture is complete for the step's value-preservation purpose: the
per-modelo service result equals `aggregate_counterpart_349`, and the counterpart
mesh resolver's binding values equal the live M349 registry projection of that prior
aggregate, including the existing payable-summary mirror fold. Verification passed
for ruff, py-compile, the focused M349 gate, and the full
counterpart/per-modelo aggregation test surface (`32 passed`).

`P03.S21` remains unchecked because the 347 half is still blocked at HEAD. Modelo 347
has no declared counterpart-source registry bindings, while
`CounterpartAggregationSourceResolver` activates from `_counterpart_sources_for_revision`.
The current M347 snapshot therefore resolves empty before a non-empty
`aggregate_counterpart_347` output can be compared. Closing that half would require
committed M347 counterpart-source registry modelling, or a coordinator-approved
change to the resolver activation contract. Both are outside `P03.S21`'s test-only
scope, and the program freeze forbids ad hoc resolver-convention changes.

Formal blocker: `DFR-D9-P03-S21-M347-COUNTERPART-SOURCE-MODELLING`. Named follow-up:
decide and author M347 counterpart-source registry modelling, then rerun `P03.S21`
against a real 347 fixture and only then check the step.

`P03.S20` also gained partial correctness evidence. The new M720 fixture proves the
per-modelo service output equals `aggregate_foreign_assets_720`, and the prior
aggregate projects through the live M720 registry to the exact expected row-indexed
binding values for two declarable account rows while excluding a sub-threshold
security control. The resolver selects the same declarable provenance and ledger
transaction id.

`P03.S20` remains unchecked because the live source-mesh envelope still has no
row-indexed binding-value channel for the M720 resolver to return that exact
projection. `ForeignAssetsAggregationSourceResolver` validates the row values against
the live registry and discards them; it returns only provenance and transaction ids.
Checking S20 would therefore overclaim that the live mesh resolution carries the prior
aggregate output exactly. Formal blocker:
`DFR-D9-P03-S20-M720-ROW-INDEXED-ENVELOPE`. Named follow-up: decide the M720 row
carrier strategy, then expose the row projection through the mesh and rerun S20.

`P03.S12` remains blocked by ordering: the plan requires S20 and S21 to pass before
enrolling the counterpart and foreign-assets resolvers. With S20/S21 formally
blocked, enrollment would deliberately put incomplete shape-C resolvers onto the live
calculate path. No `_calculation_actions.py` edit was made.

`P03.S13`, `P03.S19`, and `P03.S14` remain blocked by a retenciones contract
mismatch in the current plan text. `aggregate_per_modelo` is a pure service over
explicit command observations and returns `RetencionesAggregation`. The live
`RetencionesAggregationSourceResolver` reads the persisted per-perceptor retención
store and returns `CalculationSourceResolution` binding values. It also covers the
registry-backed source family for M111/M115/M180/M193, while `P03.S19` asks for
111/115/123/180/190/193 parity. Forcing the service branch to delegate to that
resolver would either change the service from a pure command projection into a store
reader, or reconstruct a `RetencionesAggregation` from binding values and preserve the
second aggregation shape the cleanup is supposed to remove.

Formal blockers:
`DFR-D9-P03-S13-RETENCIONES-SERVICE-MESH-CONTRACT`,
`DFR-D9-P03-S19-RETENCIONES-SIX-MODELO-PARITY-GATE`, and
`DFR-D9-P03-S14-CLI-AGGREGATE-PROJECTION-SCOPE`. Named follow-up: adjudicate whether
the CLI aggregate verb remains a pure preview over explicit observations, becomes a
store-backed mesh projection, or is retired; only then update the retenciones service
rows and author the parity gate against the chosen contract.

## 2026-07-04 D9 Status Refresh

Current `vault plan status 2026-06-26-binding-resolver-contract-unification-plan
--json` reports 16 of 21 steps complete, `next_open_step` = `P03.S21`, and
`exec_missing_ids` = `[]`. The open rows at HEAD are `P03.S21`, `P03.S20`,
`P03.S12`, `P03.S14`, and `P05.S18`.

The prior retenciones blocker is superseded by landed work. `P03.S13` and
`P03.S19` now have 2026-07-04 exec records and are checked in the plan. Current
code confirms the intended shape: `aggregate_per_modelo` delegates retenciones
aggregation to `RetencionesAggregationSourceResolver.aggregate`, and the CLI
aggregate command delegates aggregation to `aggregate_per_modelo` while
retenciones persistence goes through `persist_retencion_observations`.

`P03.S21` remains a formal deferral, not a coding gap. Modelo 347 still has no
declared counterpart-source registry bindings under its current revision, so the
counterpart resolver's registry-driven activation path is empty for 347. The
M349 half has evidence in the existing S21 exec record. The named blocker remains
`DFR-D9-P03-S21-M347-COUNTERPART-SOURCE-MODELLING`; the follow-up is M347
counterpart-source registry modelling or a coordinator-approved activation change,
then a real 347 oracle fixture.

`P03.S20` also remains formally deferred. Modelo 720 has `foreign_asset`
bindings and the existing S20 exec record proves aggregate-to-registry-row
projection, but `ForeignAssetsAggregationSourceResolver` still validates the
row-indexed binding values and discards them because the live
`CalculationSourceResolution` envelope has no row-indexed value channel. The named
blocker remains `DFR-D9-P03-S20-M720-ROW-INDEXED-ENVELOPE`; the follow-up is a
coordinator-approved M720 row carrier strategy before exposing those rows through
the mesh.

`P03.S12` remains ordered behind S20 and S21. It must not enroll counterpart or
foreign-assets resolvers, and must not remove `FOREIGN_ASSET` from
`DEFERRED_SOURCE_KINDS`, while the source-kind deferrals ADR continues to
re-ratify `foreign_asset` with no promotion date and a requirement for its own
grounded design ADR.

`P03.S14` now has focused execution evidence. The live aggregate command has moved
from the plan's older `_modelo.py` path into `_modelo_aggregate_cli.py`; the entrypoint
delegates aggregation to `aggregate_per_modelo`, delegates retenciones persistence to
`persist_retencion_observations`, and does not call the family-specific aggregation
cores directly. This pass added the missing S14 exec record, updated the backend-boundary
gate to treat `_modelo_aggregate_cli.py` as the one canonical aggregate command module,
and verified the focused CLI/service surface. The S14 checkbox remains unchecked only
because the plan file carries non-authored WIP, so mutating it would violate the
shared-worktree safety rule.

RAG discovery could not be refreshed during this pass because the singleton
`vaultspec-rag` service on port 8766 was crashed while still owned by a live
resident Python process. The pass therefore records the failed RAG attempt and
uses targeted registry/file/API confirmation only; no source edit was made from
semantic-search-only evidence.

## Closure Decision

The original close-blocker decision above records the pre-follow-up state. Current
D9 follow-up state: `P03.S10`, `P03.S11`, `P03.S13`, and `P03.S19` are landed and
checked; `P03.S21` has an exec record with completed M349 exactness evidence and a
formal M347 blocker (`DFR-D9-P03-S21-M347-COUNTERPART-SOURCE-MODELLING`); `P03.S20`
has an exec record with completed M720 aggregate-to-registry-row evidence and a
formal row-envelope blocker (`DFR-D9-P03-S20-M720-ROW-INDEXED-ENVELOPE`). The vault
plan remains open; `P03.S12` is ordered behind those blocked gates, `P03.S14` has
matching exec evidence but awaits a peer-clean checkbox mutation, and `P05.S18`
cannot run until the P03 remainder is reconciled. The bindings freeze is not liftable
from this campaign.

## Recommendations

Do not check `P03.S21` until a real M347 counterpart-source model exists and a 347
fixture proves exact resolver-vs-aggregate parity. Do not check `P03.S20` until the
M720 row projection is returned through the live mesh rather than only validated
internally. Do not run `P03.S12` while those gates remain deferred. Check `P03.S14`
only after the plan-file WIP clears and no newer source drift invalidates the exec
evidence. Do not lift the bindings freeze from this campaign: `vault plan status`
still reports open steps.
