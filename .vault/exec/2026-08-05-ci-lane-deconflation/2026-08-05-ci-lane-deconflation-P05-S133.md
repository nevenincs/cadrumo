---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:38eb6eb1fe9a99405eed4f1384d6d171be84a01eee8c1a77af07433d04ecd837'
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
- `verify:` `uv run --no-sync ruff check src/cadrumo/application/aggregation/tests/test_iva_ledger.py src/cadrumo/application/aggregation/tests/test_iva_ledger_candidates.py` -> pass
- `verify:` `uv run --no-sync ruff format --check src/cadrumo/application/aggregation/tests/test_iva_ledger.py src/cadrumo/application/aggregation/tests/test_iva_ledger_candidates.py` -> pass
- `verify:` `uv run --no-sync pytest -n 0 src/cadrumo/application/aggregation/tests/test_iva_ledger.py src/cadrumo/application/aggregation/tests/test_iva_ledger_candidates.py` -> pass
- `verify:` `uv run --no-sync python -c "from cadrumo.tests import MODULE_POLICY, measure_module_lines; measures=measure_module_lines(); targets=(''src/cadrumo/application/aggregation/tests/test_iva_ledger.py'',''src/cadrumo/application/aggregation/tests/test_iva_ledger_candidates.py''); print(''default module ceiling:'', MODULE_POLICY.default_limit); [print(path, measures[path]) for path in targets]"` -> pass
