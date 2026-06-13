---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S64'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W03.P07.S64 Registry Binding Verification

Scope: `src/aeat/domain/calculations/registry/tests/test_*binding*`, `src/aeat/domain/calculations/registry/tests`.

## Description

- Verified lint and import compatibility for split registry binding modules.
- Verified invoice, counterpart, ledger, detail-record, selector-shape, and withholding binding behavior through focused real tests.
- Restored explicit neutral previous-filing fixture input in the Renta ledger expense binding test.
- Confirmed public registry facade imports still resolve through `aeat.domain.calculations.registry`.

## Outcome

Focused binding verification passed:

- `uv run --no-sync ruff check` passed for registry binding modules and the touched Renta expense test.
- `uv run --no-sync python -m compileall` passed for the split registry binding modules.
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/tests/test_invoice_bindings.py src/aeat/domain/calculations/registry/tests/test_counterpart_bindings.py src/aeat/domain/calculations/registry/tests/test_ledger_iva_aggregation_binding.py src/aeat/domain/calculations/registry/tests/test_ledger_oss_aggregation_binding.py src/aeat/domain/calculations/registry/tests/test_ledger_renta_expense_binding.py src/aeat/domain/calculations/registry/tests/test_modelo_100_retenciones_binding_wiring.py -q` passed: 83 tests.
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/tests/test_detail_record_observations.py src/aeat/domain/calculations/registry/tests/test_detail_record_row_builders.py src/aeat/domain/calculations/registry/tests/test_selector_shape.py -q` passed: 42 tests.
- Registry facade smoke import passed for invoice, counterpart, IVA ledger, withholding, and rounding-code exports.

## Notes

`uv run --no-sync pytest src/aeat/domain/calculations/registry/tests -q -n auto` was also attempted. It completed with 2183 passed and 39 failures unrelated to the binding split: stale path-gate assumptions, existing Modelo 100/200 bound-input fixture gaps, registry data drift gates, workbook parity baseline growth, schema hygiene drift, and tautology-gate findings across other modules.
