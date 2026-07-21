---
tags:
  - '#adr'
  - '#modelo-720-prior-year-baseline'
date: '2026-07-05'
modified: '2026-07-05'
related:
  - "[[2026-07-05-modelo-720-prior-year-baseline-plan]]"
  - "[[2026-07-05-modelo-720-prior-year-baseline-adr]]"
  - "[[2026-05-20-calculation-source-connectivity-adr]]"
  - "[[2026-06-02-modelo-720-prior-year-baseline-research]]"
---

# `modelo-720-prior-year-baseline` adr: `M720 row-carrier source mesh` | (**status:** `proposed`)

## Problem Statement

Modelo 720 now has a correct row taxonomy and a resolver that can validate
declarable foreign-asset rows against the live registry. The remaining blocker
is the carrier: `resolve_foreign_asset_binding_row_values` returns values keyed
as `(binding_id, row_index)`, but `CalculationSourceResolution.binding_values`
is a scalar binding channel keyed only by `binding_id`. The M720 resolver
therefore validates the row projection and discards it, preserving only
provenance and source transaction ids. That is honest but insufficient for live
mesh enrollment, draft replay, or export parity.

This ADR decides how row-indexed Modelo 720 binding values move through the
source mesh and calculation/draft surfaces without flattening repeat rows into
fake scalar binding ids and without repurposing unrelated detail-row DTOs.

## Considerations

- The registry row-binding resolver already has the correct M720 value shape:
  a real `BindingId`, a 1-based row index, and a scalar field value. That is the
  same identity that the filing draft surface already models through
  `ModeloBindingValue.row_index`.
- `CalculationSourceResolution` currently has scalar binding channels
  (`binding_values`, `enum_binding_values`, `date_binding_values`) and a
  `detail_rows` channel. The scalar channels cannot represent repeat rows
  without corrupting the binding-id namespace.
- `detail_rows` is not a binding-value channel. It carries typed domain row DTOs
  such as M184/M232/M347/M349 rows, is content-addressed on the calculation
  revision, and is rendered/exported as row objects. Modelo 720's registry
  output is already expressed as binding ids plus row indexes, not as a
  committed M720 domain row DTO.
- The source-connectivity ADR names `CalculationSourceResolution` as the single
  resolved-source carrier and already anticipated detail-row data. The missing
  piece is the row-indexed binding-value channel that bridges registry row
  bindings to draft/replay/export.
- The D9 resolver-contract audit explicitly blocked M720 promotion because the
  foreign-assets resolver had no row-indexed envelope channel. This decision is
  the named follow-up for that blocker.

## Considered options

- Flatten repeat rows into synthetic scalar binding ids such as
  `binding_id:row-1`. Rejected because it invents registry identifiers the
  registry does not declare, bypasses binding-id validation, and makes row order
  part of a string convention instead of typed state.
- Reuse `detail_rows` and add a Modelo 720 row DTO. Rejected for this campaign
  because it duplicates the registry row-binding resolver output and loses the
  direct `BindingId` -> row field relationship the draft/export layer needs.
- Add a first-class row-indexed binding-value map to
  `CalculationSourceResolution`. Chosen because it preserves real registry
  binding ids, carries the 1-based row index as typed data, composes with the
  existing merge envelope, and projects directly to `ModeloBindingValue` records
  with `row_index`.

## Constraints

- No new binding source kind, resolver convention, validator convention, or
  registry grouping is introduced. `foreign_asset` remains the source kind and
  `per_foreign_asset` remains the row grouping.
- The carrier must preserve the exact registry `BindingId`; the row index is a
  separate typed coordinate and must be 1-based.
- The scalar calculation engine remains scalar. Row-indexed binding values are
  for draft/replay/export and live-mesh parity, not formula-runtime inputs.
- Merge semantics must stay exclusive by `(binding_id, row_index)`. Two
  resolvers may not claim the same row-binding coordinate in the same mesh tier.
- The parent features are stable enough to build on: the source mesh is the
  canonical resolver envelope, the filing draft already supports
  `ModeloBindingValue.row_index`, and the foreign-asset registry row resolver is
  real-behavior tested against live M720 bindings.

## Implementation

Add a row-indexed binding-value channel to the source mesh envelope. The channel
is a typed map whose key is `(BindingId, row_index)` and whose value is the
registry row field scalar (`Decimal` or `str` for the current M720 resolver).
The field should be named for binding values, not detail rows, so consumers do
not confuse it with `detail_rows`.

`merge_source_resolutions` and the precedence merge carry this map just like
the scalar binding channels, but collision detection is keyed by the full
`(binding_id, row_index)` coordinate. The foreign-assets resolver returns the
validated output from `resolve_foreign_asset_binding_row_values` through this
channel.

The calculation/draft assembly layer carries the row-indexed values into
`ModeloBindingValue` with the same `binding_id`, the scalar value, the binding's
legal/source refs, `source = foreign_asset`, and the row index. Replay/export
must preserve the row coordinate as a structured field; it must not join the row
number into the binding id string.

## Rationale

The chosen carrier is the smallest shape that preserves the registry contract
end to end. The domain resolver already returns `(BindingId, row_index)` because
that is the actual identity of a field in a repeating record. Carrying that
shape through the mesh prevents two silent failures: scalar collapse, where
only one row survives per binding id, and synthetic-id drift, where downstream
code treats fabricated keys as registry facts.

Reusing `detail_rows` is attractive because it already travels through the mesh,
but it is the wrong abstraction for M720 binding parity. `detail_rows` carries
domain row DTOs whose fields are exported as row objects. The M720 blocker is
not missing a row DTO; it is missing the ability to move registry-declared
row-binding values from a resolver into draft/replay/export with their binding
grounding intact.

## Consequences

- The M720 resolver can stop discarding validated registry row values and can
  prove live mesh parity against the per-modelo aggregation output.
- Draft and replay surfaces can carry row-indexed binding values using the
  existing `ModeloBindingValue.row_index` concept.
- The calculation engine remains scalar; formulas do not consume row-indexed
  M720 detail fields unless a separate ADR later decides a formula-facing row
  fold.
- Merge and serialization code must gain tests for collision handling,
  deterministic ordering, and JSON-safe replay of tuple-keyed row coordinates.
- This ADR unlocks W03 implementation and later `FOREIGN_ASSET` enrollment, but
  it does not itself remove `FOREIGN_ASSET` from the deferred source set.
