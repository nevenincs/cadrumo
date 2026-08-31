---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:d3095e4eef3afd4a1c5c2f81e8b1d9d6fd46e7169bbd32266decd5032a784b0e'
step_id: 'S135'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
# Refactor the size-budget subjects in test_renta_ledger.py into cohesive siblings without raising any threshold.

## Scope

- `src/cadrumo/application/aggregation/tests/test_renta_ledger.py`

## Changes

- `M` `src/cadrumo/application/aggregation/tests/test_renta_ledger.py`
- `A` `src/cadrumo/application/aggregation/tests/test_renta_ledger_prorrata_repository.py`

## Notes

- `uv run --no-sync ruff check src/cadrumo/application/aggregation/tests/test_renta_ledger.py src/cadrumo/application/aggregation/tests/test_renta_ledger_prorrata_repository.py` printed `All checks passed!`; exit `0`.
- `uv run --no-sync ruff format --check src/cadrumo/application/aggregation/tests/test_renta_ledger.py src/cadrumo/application/aggregation/tests/test_renta_ledger_prorrata_repository.py` printed `2 files already formatted`; exit `0`.
- Marker-free collection used `uv run --no-sync pytest -n 0 --collect-only -q src/cadrumo/application/aggregation/tests/test_renta_ledger.py src/cadrumo/application/aggregation/tests/test_renta_ledger_prorrata_repository.py`; it printed `33 tests collected in 1.43s`; exit `0`. The command contains no `-m`, `-k`, `--ignore`, or other selector, so raw collection is `33` and deselected is `0`.
- Initial sequential execution found the extracted module omitted the shared fixture's required `_BUCKET_ID` marker: `30 passed, 3 errors in 21.96s`, exit `1`, with `RuntimeError: secure_objects requires a non-empty module _BUCKET_ID`. S135 added `_BUCKET_ID = SECURE_OBJECTS_BUCKET_ID`; it is the fixture's real module contract, not a product shim.
- Sequential retry used `uv run --no-sync pytest -n 0 src/cadrumo/application/aggregation/tests/test_renta_ledger.py src/cadrumo/application/aggregation/tests/test_renta_ledger_prorrata_repository.py`; it printed `33 passed in 24.83s`; exit `0`.
- Size proof used `uv run --no-sync python -c "from cadrumo.tests import MODULE_POLICY, measure_module_lines; measures = measure_module_lines(); targets = ('src/cadrumo/application/aggregation/tests/test_renta_ledger.py', 'src/cadrumo/application/aggregation/tests/test_renta_ledger_prorrata_repository.py'); print(f'default module ceiling: {MODULE_POLICY.default_limit}'); [print(f'{path}: {measures[path]} <= {MODULE_POLICY.default_limit}') for path in targets]"`; it printed `default module ceiling: 1250`, `src/cadrumo/application/aggregation/tests/test_renta_ledger.py: 1216 <= 1250`, and `src/cadrumo/application/aggregation/tests/test_renta_ledger_prorrata_repository.py: 298 <= 1250`; exit `0`. No size policy or baseline path was changed by S135.
