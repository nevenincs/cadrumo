---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:4667c286d344985ff61c7067799c729138bf117bcc8376f672eafc559055e4cd'
step_id: 'S134'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
# Refactor the size-budget subjects in test_modelo_source_mesh_ledger.py into cohesive siblings without raising any threshold.

## Scope

- `src/cadrumo/application/aggregation/tests/test_modelo_source_mesh_ledger.py`

## Changes

- `M` `src/cadrumo/application/aggregation/tests/test_modelo_source_mesh_ledger.py`
- `A` `src/cadrumo/application/aggregation/tests/test_modelo_source_mesh_recargo.py`

## Notes

- `uv run --no-sync ruff check src/cadrumo/application/aggregation/tests/test_modelo_source_mesh_ledger.py src/cadrumo/application/aggregation/tests/test_modelo_source_mesh_recargo.py` printed `All checks passed!`; exit `0`.
- `uv run --no-sync ruff format --check src/cadrumo/application/aggregation/tests/test_modelo_source_mesh_ledger.py src/cadrumo/application/aggregation/tests/test_modelo_source_mesh_recargo.py` printed `2 files already formatted`; exit `0`.
- Marker-free collection used `uv run --no-sync pytest -n 0 --collect-only -q src/cadrumo/application/aggregation/tests/test_modelo_source_mesh_ledger.py src/cadrumo/application/aggregation/tests/test_modelo_source_mesh_recargo.py`; it printed `21 tests collected in 2.22s`; exit `0`. The command contains no `-m`, `-k`, `--ignore`, or other selector, so raw collection is `21` and deselected is `0`.
- Full sequential execution used `uv run --no-sync pytest -n 0 src/cadrumo/application/aggregation/tests/test_modelo_source_mesh_ledger.py src/cadrumo/application/aggregation/tests/test_modelo_source_mesh_recargo.py`; it exited `1` with `1 failed, 20 passed in 60.34s`. The unchanged `test_iva_source_mesh_withholds_received_invoice_without_deduction_authority` failed because `_modelo_bindings_invoice_iva_refusal.py` now raised `AggregationValidationError`; no S134-owned path was changed to conceal or repair that external source-mesh behaviour.
- The extracted recargo sibling ran with `uv run --no-sync pytest -n 0 src/cadrumo/application/aggregation/tests/test_modelo_source_mesh_recargo.py`; it printed `2 passed in 36.32s`; exit `0`.
- Size proof used `uv run --no-sync python -c "from cadrumo.tests import MODULE_POLICY, measure_module_lines; measures = measure_module_lines(); targets = ('src/cadrumo/application/aggregation/tests/test_modelo_source_mesh_ledger.py', 'src/cadrumo/application/aggregation/tests/test_modelo_source_mesh_recargo.py'); print(f'default module ceiling: {MODULE_POLICY.default_limit}'); [print(f'{path}: {measures[path]} <= {MODULE_POLICY.default_limit}') for path in targets]"`; it printed `default module ceiling: 1250`, `src/cadrumo/application/aggregation/tests/test_modelo_source_mesh_ledger.py: 1145 <= 1250`, and `src/cadrumo/application/aggregation/tests/test_modelo_source_mesh_recargo.py: 189 <= 1250`; exit `0`. No size policy or baseline path was changed by S134.
