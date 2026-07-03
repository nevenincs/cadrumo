---
tags:
  - '#exec'
  - '#eoy-final-calculation'
date: '2026-06-30'
modified: '2026-06-30'
step_id: 'S06'
related:
  - "[[2026-06-22-eoy-final-calculation-plan]]"
---

# Add M100 and M390 annual continuity regression coverage asserting the headline figure derives from period/ledger inputs, mirroring the M130 carry-forward tests

## Scope

- `src/aeat/application/modelo/tests`

## Description

- Ground current implementation with `uvx vaultspec-rag search "M100 non-first-slice gastos advisory parity 2025 annual continuity regression M390 headline figure derives from period inputs" --type code`.
- Verify M100 annual live tests derive annual figures from filed period observations and ledger inputs.
- Verify M390 annual live tests derive reconciliation and compensation figures from filed M303 quarters and the annual partition resolver.

## Outcome

- `test_e2e_ledger_m130_quarters_to_m100_annual.py` covers the full yearly cadence from persisted ledger rows through four M130 quarters into M100 annual calculation.
- `test_modelo_100_pagos_fraccionados_fold_in_live.py` asserts M100 casilla `0604` derives from four distinct filed M130 quarterly values plus true-zero M131 quarters, and leaves the value unresolved with diagnostics when prior filings are partial or absent.
- `test_modelo_100_2025_expense_inspection_live.py` confirms M100/2025 work creation and live bucket aggregation expose first-slice expense casillas `0186` and `0199` from real ledger transactions.
- `test_modelo_390_303_fold_in_live.py` asserts M390 annual reconciliation values derive from four distinct filed M303 quarters and that compensation boxes derive from `iva_compensation_annual_partition`.
- Verification passed in `uv run --no-sync pytest -q --tb=short src/aeat/domain/renta/tests/test_first_slice_routing.py src/aeat/domain/calculations/registry/tests/test_ledger_renta_expense_binding.py src/aeat/application/modelo/tests/test_e2e_ledger_m130_quarters_to_m100_annual.py src/aeat/application/modelo/tests/test_modelo_100_pagos_fraccionados_fold_in_live.py src/aeat/application/modelo/tests/test_modelo_100_2025_expense_inspection_live.py src/aeat/application/modelo/tests/test_modelo_390_303_fold_in_live.py`: 21 passed.

## Notes

- No code change was needed for S06; this record closes the current-state evidence for already landed regression coverage.
