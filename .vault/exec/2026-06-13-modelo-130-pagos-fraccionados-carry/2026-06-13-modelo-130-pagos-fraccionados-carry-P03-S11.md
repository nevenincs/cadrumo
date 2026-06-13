---
tags:
  - '#exec'
  - '#modelo-130-pagos-fraccionados-carry'
date: '2026-06-13'
modified: '2026-06-13'
step_id: 'S11'
related:
  - "[[2026-06-13-modelo-130-pagos-fraccionados-carry-plan]]"
---




# encode the casilla-16 filed-zero-vs-not-captured distinction: a prior observation carrying casilla 16 = 0 is a no-op, a prior observation lacking any casilla-16 entry lets the carry proceed but raises a non-blocking advisory naming the gap, never silently dropping the minoracion

## Scope

- `src/aeat/application/modelo/_prior_payment_advisory.py`

## Description

- Encoded the casilla-16 filed-zero-vs-not-captured distinction: `_optional_source_casilla_ids` marks the minoración casilla (16) optional for the `prior_pagos_fraccionados` op, so `_observed_casilla_values` defaults an absent 16 to zero rather than hard-failing (the positive-part casilla 07 stays required).
- Added `collect_prior_payment_minoracion_not_captured_diagnostics` raising a non-blocking `prior_payment_minoracion_not_captured` advisory when a prior filing carries casilla 07 but no casilla-16 entry; wired it onto the calculate path and registered the new diagnostic reason.

## Outcome

A not-captured minoración lets the carry proceed (absent 16 -> 0) but surfaces the gap as a non-blocking advisory; a filed-zero casilla 16 is a silent no-op. Verified by `test_modelo_130_prior_payment_advisory.py` (3 passed) and `test_modelo_130_casilla_05_carry.py::test_not_captured_minoracion...`. Landed in commit `02e9bfb65`.

## Notes

The resolver tolerance is scoped strictly to the minoración slot of the `prior_pagos_fraccionados` op; every other binding/casilla still hard-fails on a missing source casilla.
