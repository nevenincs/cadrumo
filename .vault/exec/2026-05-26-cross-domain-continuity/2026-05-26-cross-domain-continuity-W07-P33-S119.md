---
step_id: S119
tags:
  - "#exec"
  - "#cross-domain-continuity"
date: 2026-05-27
modified: '2026-05-27'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-05-26-cross-domain-continuity-W07-P33-S118]]"
---

# cross-domain-continuity W07.P33.S119 — compare verb regression test

## Outcome

Regression test written, passing (1/1), lint-clean, type-clean at
`src/aeat/entrypoints/cli/test_modelo_compare.py`.

Commit: `e934f020d`

## What was done

Created `test_modelo_compare_m130_two_year_delta_rows` using the
`isolated_runtime_profile` / `TestRuntimeProfile` fixture pattern.

### Test strategy (non-tautological)

Uses Modelo 130 (`2019-y-siguientes`) for years 2025 and 2026 — M130 requires
only simple bindings so both years can produce complete `CalculationRevision`
records.

**Drive side**: creates M130 work units for 2025 (ingresos=12,000) and 2026
(ingresos=20,000) via CLI, calculates each.  Invokes
`aeat app modelo compare --year 2025 --year 2026 --modelo 130`.

**Oracle side**: the `work calculate` JSON payloads captured before the compare
call provide `year_a_value` and `year_b_value` for each casilla.  The compare
verb must surface `delta = year_b - year_a`.

These are independent code paths: compare reads stored `CalculationRevision`
records; the oracle captures values from the same `work calculate` surface.

### Assertions

- `year_a == 2025`, `year_b == 2026`, `modelo == "130"`
- Key result casillas (03, 04, 07, 19) oracle verify (non-zero expected delta
  given materially different ingresos)
- Oracle values confirmed against AEAT DR 130 Instrucciones:
  - 2025 casilla 07 = 1,600 EUR (20% x (12,000 - 4,000))
  - 2026 casilla 07 = 3,200 EUR (20% x (20,000 - 4,000))

### Anti-tautology

Casilla 02 (gastos) is identical in both years (4,000 EUR). Its delta row
must be exactly zero, proving the compare verb does not manufacture
differences for equal values.

## Files changed

- `src/aeat/entrypoints/cli/test_modelo_compare.py` (NEW, 300 lines)
