---
tags:
  - '#exec'
  - '#modelo-720-prior-year-baseline'
date: '2026-07-05'
modified: '2026-07-17'
step_id: 'S12'
related:
  - "[[2026-07-05-modelo-720-prior-year-baseline-plan]]"
---

# Author the M720 row-carrier ADR deciding how row-indexed binding values flow through the source mesh and export draft surfaces

## Scope

- `.vault/adr/`

## Description

- Grounded the row-carrier decision with semantic code and vault searches for M720 row-indexed binding values, source mesh carriers, foreign-asset resolver output, and scalar binding ids.
- Confirmed `resolve_foreign_asset_binding_row_values` already returns row values keyed as `(binding_id, row_index)`.
- Confirmed `CalculationSourceResolution.binding_values` is scalar and the current foreign-assets resolver validates the row values but discards them.
- Confirmed `detail_rows` exists in the source mesh but carries domain row DTOs, not registry binding ids plus row indexes.
- Authored `2026-07-05-modelo-720-row-carrier-adr.md` as a proposed row-carrier ADR.

## Outcome

- The ADR chooses a first-class row-indexed binding-value map keyed by the real registry `BindingId` plus a typed 1-based row index.
- The ADR rejects scalar synthetic binding ids and rejects overloading `detail_rows` for M720 binding-value parity.
- The ADR requires merge collision detection by full `(binding_id, row_index)` coordinate and projection to `ModeloBindingValue.row_index` for draft/replay/export.

## Notes

- The vault CLI cannot scaffold two ADRs with the same date and feature stem, so the ADR file uses the unique stem `2026-07-05-modelo-720-row-carrier-adr` while retaining the `modelo-720-prior-year-baseline` feature tag.
- No source code migration was performed in S12; W03.P05 owns the implementation.
