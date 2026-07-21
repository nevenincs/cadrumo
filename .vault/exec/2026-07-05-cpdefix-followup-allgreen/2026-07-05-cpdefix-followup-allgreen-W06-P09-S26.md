---
tags:
  - '#exec'
  - '#cpdefix-followup-allgreen'
date: '2026-07-06'
modified: '2026-07-06'
step_id: 'S26'
related:
  - "[[2026-07-05-cpdefix-followup-allgreen-plan]]"
---
# Execution Notes

## Grounding
- RAG search: `uvx vaultspec-rag search "application_adapter_exports calculation revision work unit modelo record attachment store secure object repository modelo tests real source" --type code --max-results 12`.
- Concrete sources confirmed from `src/aeat/tests/application_adapter_exports.py` and adapter modules:
  - `BucketEventHistoryRepository` -> `src/aeat/adapters/persistence/profile/buckets`
  - `CalculationRevisionCatalogueRepository` -> `src/aeat/adapters/persistence/profile/modelos_calculation`
  - `WorkUnitCatalogueRepository` -> `src/aeat/adapters/persistence/profile/modelos_work_units`
  - `InvoiceCatalogueRepository` -> `src/aeat/adapters/persistence/profile/invoices`
  - `TransactionCatalogueRepository` -> `src/aeat/adapters/persistence/profile/transactions`
  - `SecureObjectRepository` -> `src/aeat/adapters/persistence/storage/sql`

## Change
Replaced the remaining calculation/modelo application tests that imported concrete repositories through `src/aeat/tests/application_adapter_exports.py` with direct imports from their real adapter source modules.

Touched files:
- `src/aeat/application/calculations/tests/test_modelo_100_base_negativa_general_compensation.py`
- `src/aeat/application/calculations/tests/test_modelo_130_multiyear_renta_enrollment.py`
- `src/aeat/application/calculations/tests/test_pull_path_calculate_path_casilla_parity.py`
- `src/aeat/application/modelo/tests/test_modelo_100_2025_retenciones_credit_fold_in_live.py`
- `src/aeat/application/modelo/tests/test_modelo_202_2025_pago_fraccionado_manual_worked_example.py`
- `src/aeat/application/modelo/tests/test_modelo_200_2024_ejemplo1_tributacion_minima_manual_worked_example.py`

## Verification
- `uv run --no-sync ruff check src/aeat/application/calculations/tests/test_modelo_100_base_negativa_general_compensation.py src/aeat/application/calculations/tests/test_modelo_130_multiyear_renta_enrollment.py src/aeat/application/calculations/tests/test_pull_path_calculate_path_casilla_parity.py src/aeat/application/modelo/tests/test_modelo_100_2025_retenciones_credit_fold_in_live.py src/aeat/application/modelo/tests/test_modelo_202_2025_pago_fraccionado_manual_worked_example.py src/aeat/application/modelo/tests/test_modelo_200_2024_ejemplo1_tributacion_minima_manual_worked_example.py` -> passed.
- `uv run --no-sync pytest -q src/aeat/application/calculations/tests/test_modelo_100_base_negativa_general_compensation.py src/aeat/application/calculations/tests/test_modelo_130_multiyear_renta_enrollment.py src/aeat/application/calculations/tests/test_pull_path_calculate_path_casilla_parity.py src/aeat/application/modelo/tests/test_modelo_100_2025_retenciones_credit_fold_in_live.py src/aeat/application/modelo/tests/test_modelo_202_2025_pago_fraccionado_manual_worked_example.py src/aeat/application/modelo/tests/test_modelo_200_2024_ejemplo1_tributacion_minima_manual_worked_example.py -n 0` -> `23 passed`.
- `rg -n "tests\.application_adapter_exports|application_adapter_exports import" <six touched files>` -> no remaining hits.
