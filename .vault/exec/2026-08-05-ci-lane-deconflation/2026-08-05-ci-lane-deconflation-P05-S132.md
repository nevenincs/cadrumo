---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:54d39615602750b651dbadd7825e41d48cda67a88cc8ccb6d9e048d0e291fec0'
step_id: 'S132'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
# Refactor the size-budget subjects in _source_mesh.py into cohesive siblings without raising any threshold.

## Scope

- `src/cadrumo/application/aggregation/_source_mesh.py`

## Changes

- `A` `src/cadrumo/application/aggregation/source_resolution_operations.py`
- `M` `src/cadrumo/application/aggregation/__init__.py`
- `M` `src/cadrumo/application/aggregation/_modelo_bindings_renta_expenses.py`
- `M` `src/cadrumo/application/aggregation/_modelo_bindings_retenciones.py`
- `M` `src/cadrumo/application/aggregation/_oss_ioss.py`
- `M` `src/cadrumo/application/aggregation/_withholding_source.py`
- `M` `src/cadrumo/application/aggregation/tests/test_source_mesh.py`
- `M` `src/cadrumo/application/calculations/_bienes_inversion_regularizacion.py`
- `M` `src/cadrumo/application/calculations/_iva_compensation_annual_partition.py`
- `M` `src/cadrumo/application/calculations/_multi_year.py`
- `M` `src/cadrumo/application/calculations/_prorrata_regularizacion.py`
- `M` `src/cadrumo/application/calculations/_relation_prefill.py`
- `M` `src/cadrumo/application/invoices/_source_resolver.py`
- `M` `src/cadrumo/application/modelo/_calculation_resolution.py`
- `M` `src/cadrumo/application/modelo/_calculation_source_staging.py`
- `M` `src/cadrumo/application/modelo/borrador_binding.py`
- `M` `src/cadrumo/application/modelo/tests/test_deferred_detalle_source_advisories.py`
- `M` `src/cadrumo/application/modelo/tests/test_local_cross_period_carry.py`
- `M` `src/cadrumo/application/modelo/tests/test_relation_fold_in_live.py`
- `M` `src/cadrumo/application/modelo/tests/test_source_boundary_and_enrollment.py`
- `M` `src/cadrumo/application/modelo/tests/test_unresolved_binding_diagnostics.py`
- `M` `.vault/exec/2026-08-05-ci-lane-deconflation/2026-08-05-ci-lane-deconflation-P05-S132.md`
- `verify:` `uv run --no-sync ruff check src/cadrumo/application/aggregation/source_resolution_operations.py` -> `pass`; `RUFF_CHECK_EXIT=0`
- `verify:` `uv run --no-sync pytest --collect-only -q -o addopts= src/cadrumo/application/aggregation/tests/test_source_mesh.py` -> `60 tests collected in 3.51s`; `COLLECT_EXIT=0`; raw collection `60`; deselected `0`
- `verify:` `uv run --no-sync pytest -q -n 0 src/cadrumo/application/aggregation/tests/test_source_mesh.py` -> `60 passed in 38.88s`; `PYTEST_EXIT=0`; raw collection `60`; deselected `0`
- `verify:` `uv run --no-sync pytest -q -n 0 src/cadrumo/application/aggregation/tests/test_source_mesh.py -k "source_resolution_merge or storage_degradation_resolution"` -> `14 passed, 46 deselected in 2.20s`; `PYTEST_EXIT=0`; raw collection `60`; selected `14`; deselected `46`
- `verify:` `uv run --no-sync pytest -q -n 0 src/cadrumo/application/aggregation/tests/test_source_mesh.py src/cadrumo/application/aggregation/tests/test_modelo_source_mesh_ledger.py` -> `1 failed, 80 passed in 59.35s`; `PYTEST_EXIT=1`; raw collection `81`; deselected `0`
- `verify:` `uv run --no-sync python -c "from cadrumo.tests._size_budget import MODULE_POLICY, measure_module_lines; from cadrumo.application.aggregation.source_resolution_operations import merge_source_resolutions; path='src/cadrumo/application/aggregation/_source_mesh.py'; assert measure_module_lines()[path] <= MODULE_POLICY.default_limit; assert merge_source_resolutions.__module__ == 'cadrumo.application.aggregation.source_resolution_operations'; print(path)"` -> `src/cadrumo/application/aggregation/_source_mesh.py`; `S132_LITERAL_SIZE_IMPORT_EXIT=0`; physical size `1233 <= 1250`; baseline pin `None`

## Notes

- The source-mesh contraction is predecessor commit `06a7fbe31a`; this step adds its omitted canonical sibling and direct consumer migrations without changing the 1250-line policy or baseline.
- The 81-node source-mesh command failed only at `test_iva_source_mesh_withholds_received_invoice_without_deduction_authority`: S130-owned IVA-refusal extraction raised `AggregationValidationError: errors.error.error_modelo_aggregation_binding` through `_modelo_bindings.py:225` and `_modelo_bindings_invoice_iva_refusal.py:168`. Its files and the unrelated core relocation hunk in `_source_mesh.py` are intentionally excluded from this S132 commit; the accepted 60/0 and 14/46 S132 evidence remains passing.
