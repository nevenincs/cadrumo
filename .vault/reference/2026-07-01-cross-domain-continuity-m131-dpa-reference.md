---
tags:
  - '#reference'
  - '#cross-domain-continuity-m131-dpa'
date: '2026-07-01'
modified: '2026-07-17'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# `cross-domain-continuity-m131-dpa` reference: `M131 DPA/page_1 calculation bridge reference`

Research grounded `W09.P41.S297`, the M131 objective-estimation fixed-record
inputs, and the calculation runtime path that currently leaves those inputs out
of liquidation casillas. Sources consulted were the cross-domain continuity plan,
the calculation-truth registry rebuild plan, RAG code hits for M131 DPA bindings,
the 2024-2026 M131 registry files, export-support tests, and the registry formula
runtime.

## Summary

M131 currently models page activity fields and DPA module fields as structured
fixed-record `manual_input` bindings. The 2026 binding file defines page activity
fields under the `page_1` record and DPA module units/rendimiento fields under
the `DPA` record; the 2024 and 2025 revisions carry year-prefixed equivalents.
These bindings support draft/export surfaces, as shown by
`src/aeat/application/filing/tests/_export_support.py`, but they are not
calculation casillas.

Liquidation formulas remain separate. For the active M131 revisions, casilla
`04` is the official no-datos-base branch, calculated from casilla `03` using
the objective no-base fractional payment rate. Casilla `07` then sums `02`,
`04`, and `06`. The S297 testimony phrase "casilla 04 equals casilla 01 times
casilla 02 divided by 100" appears to refer to activity-row field semantics, not
the liquidation casilla `04`. A fix must not repurpose liquidation `04`.

The registry runtime accepts arbitrary binding values, but a binding affects a
formula only when a formula references it. Manual casillas default to zero when
no casilla input is supplied, and bound-input projection only walks casillas
declared with `input_kind = bound`. As a result, supplying only DPA module
bindings or only page activity bindings to `calculate_registry_snapshot` leaves
casillas `01`, `02`, `04`, `07`, `10`, `13`, and `15` at zero.

The missing capability is therefore a narrow M131 bridge from objective-
estimation datos-base activity inputs into liquidation casillas `01` and `02`,
with downstream totals following through existing formulas. A global projection
of every fixed-record `manual_input` binding into casillas would be unsafe across
modelos. If full DPA module coefficient calculation requires annual Orden
modulos tables not yet modeled, the honest closure is to implement only the
grounded bridge and leave the coefficient-table oracle as a residual follow-up.
