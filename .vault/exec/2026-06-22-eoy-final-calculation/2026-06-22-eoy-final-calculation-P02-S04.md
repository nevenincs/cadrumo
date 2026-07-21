---
tags:
  - '#exec'
  - '#eoy-final-calculation'
date: '2026-06-30'
modified: '2026-06-30'
step_id: 'S04'
related:
  - "[[2026-06-22-eoy-final-calculation-plan]]"
---

# Confirm the M100 non-first-slice gastos advisory fires at parity with 2025 (no code unless missing)

## Scope

- `src/aeat/_data/registry/aeat/modelos/100`

## Description

- Ground current implementation with `uvx vaultspec-rag search "M100 non-first-slice gastos advisory parity 2025 annual continuity regression M390 headline figure derives from period inputs" --type code`.
- Load M100 2024 and 2025 registry snapshots and compare the first-slice expense bindings.
- Run focused Renta first-slice and annual M100/M390 tests.

## Outcome

- M100/2024 and M100/2025 both bind the same four first-slice expense target casillas: `0186`, `0192`, `0199`, and `0203`.
- Both revisions use `source = "ledger_renta_expense_aggregation"` with `fact = "deductible_amount_sum"` and selectors targeting Modelo 100 annual period `0A`.
- The routing table remains closed to those four target casillas; non-first-slice expenses are not silently folded into another box. The current source diagnostic path reports unrouted non-zero observations through `ledger_renta_expense_aggregation` instead of under-declaring them.
- Verification passed in `uv run --no-sync pytest -q --tb=short src/aeat/domain/renta/tests/test_first_slice_routing.py src/aeat/domain/calculations/registry/tests/test_ledger_renta_expense_binding.py src/aeat/application/modelo/tests/test_e2e_ledger_m130_quarters_to_m100_annual.py src/aeat/application/modelo/tests/test_modelo_100_pagos_fraccionados_fold_in_live.py src/aeat/application/modelo/tests/test_modelo_100_2025_expense_inspection_live.py src/aeat/application/modelo/tests/test_modelo_390_303_fold_in_live.py`: 21 passed.

## Notes

- No code change was needed for S04; this is a current-state confirmation step.
