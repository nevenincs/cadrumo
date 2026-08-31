---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:e14111f82a4aaf56dfc5baf5d54d2169e1dfbb2b558074858495d86763583531'
step_id: 'S133'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
# Refactor the size-budget subjects in test_iva_ledger.py into cohesive siblings without raising any threshold.

## Scope

- `src/cadrumo/application/aggregation/tests/test_iva_ledger.py`

## Changes

- `M` `src/cadrumo/application/aggregation/tests/test_iva_ledger.py`
- `A` `src/cadrumo/application/aggregation/tests/test_iva_ledger_candidates.py`

## Notes

- Evidence repair after the independent review's HIGH finding. `uv run --no-sync ruff check src/cadrumo/application/aggregation/tests/test_iva_ledger.py src/cadrumo/application/aggregation/tests/test_iva_ledger_candidates.py` printed `All checks passed!`; exit `0`.
- `uv run --no-sync ruff format --check src/cadrumo/application/aggregation/tests/test_iva_ledger.py src/cadrumo/application/aggregation/tests/test_iva_ledger_candidates.py` printed `2 files already formatted`; exit `0`.
- Marker-free collection used `uv run --no-sync pytest -n 0 --collect-only -q src/cadrumo/application/aggregation/tests/test_iva_ledger.py src/cadrumo/application/aggregation/tests/test_iva_ledger_candidates.py`; it printed `42 tests collected in 3.67s`; exit `0`. The command contains no `-m`, `-k`, `--ignore`, or other selector, so raw collection is `42` and deselected is `0`.
- Sequential execution used `uv run --no-sync pytest -n 0 src/cadrumo/application/aggregation/tests/test_iva_ledger.py src/cadrumo/application/aggregation/tests/test_iva_ledger_candidates.py`; it printed `42 passed in 14.55s`; exit `0`.
- Size proof used `uv run --no-sync python -c "from cadrumo.tests import MODULE_POLICY, measure_module_lines; measures = measure_module_lines(); targets = ('src/cadrumo/application/aggregation/tests/test_iva_ledger.py', 'src/cadrumo/application/aggregation/tests/test_iva_ledger_candidates.py'); print(f'default module ceiling: {MODULE_POLICY.default_limit}'); [print(f'{path}: {measures[path]} <= {MODULE_POLICY.default_limit}') for path in targets]"`; it printed `default module ceiling: 1250`, `src/cadrumo/application/aggregation/tests/test_iva_ledger.py: 1156 <= 1250`, and `src/cadrumo/application/aggregation/tests/test_iva_ledger_candidates.py: 313 <= 1250`; exit `0`. No size policy or baseline path was changed by S133.
- Initial parallel execution used `uv run --no-sync pytest src/cadrumo/application/aggregation/tests/test_iva_ledger.py src/cadrumo/application/aggregation/tests/test_iva_ledger_candidates.py`; it exited `1` with two collection errors, both `ModuleNotFoundError: No module named 'cadrumo.core.export_layout_format'`, while a peer rename of that core module was in flight in the shared worktree. The sequential retry above completed cleanly, so this was shared-worktree timing residue, not an S133 failure.
- At review time a separate current-worktree rerun encountered `ModuleNotFoundError: No module named 'cadrumo.core.iva_category_resolution'` before either S133 test could execute. No S133-owned path provides that module; the later marker-free collection and sequential run above no longer reproduce it, so it remains external shared-WIP residue rather than a source disposition change.
