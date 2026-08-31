---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:a8a46afbf25c5cd5d02b49b6a5961ed13efef6eaf5ccc9deca8d0aa310142fd7'
step_id: 'S126'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
# Refactor the size-budget subjects in _profile_custody_carry.py into cohesive siblings without raising any threshold.

## Scope

- `src/cadrumo/adapters/persistence/storage/_profile_custody_carry.py`

## Changes

- `M` `src/cadrumo/adapters/persistence/storage/_profile_custody_carry.py`
- `verify:` `uv run --no-sync ruff check src/cadrumo/adapters/persistence/storage/_profile_custody_carry.py` -> `All checks passed!`; exit `0`
- `verify:` `uv run --no-sync ruff format --check src/cadrumo/adapters/persistence/storage/_profile_custody_carry.py` -> `1 file already formatted`; exit `0`
- `verify:` `uv run --no-sync pytest -o addopts='' -q src/cadrumo/application/user_profile/tests/test_custody_roundtrip.py src/cadrumo/application/user_profile/tests/test_custody_restore_atomicity.py` -> `7 passed in 10.46s`; 0 deselected; exit `0`
- `verify:` `uv run --no-sync pytest -o addopts='' --collect-only -q src/cadrumo/application/user_profile/tests/test_custody_roundtrip.py src/cadrumo/application/user_profile/tests/test_custody_restore_atomicity.py` -> `7 tests collected in 0.84s`; 0 deselected; exit `0`
- `verify:` `uv run --no-sync python -c "from cadrumo.tests._size_budget import measure_module_lines, measure_callable_lines; path='src/cadrumo/adapters/persistence/storage/_profile_custody_carry.py'; modules=measure_module_lines(); callables=measure_callable_lines(); print(f'module: {modules[path]} <= 1250'); print(f'_natural_key_resolvers: {callables[path + \"::_natural_key_resolvers\"]} <= 180'); print(f'_live_snapshot_natural_key_resolvers: {callables[path + \"::_live_snapshot_natural_key_resolvers\"]} <= 180'); print(f'_modelo_natural_key_resolvers: {callables[path + \"::_modelo_natural_key_resolvers\"]} <= 180'); print(f'_sede_natural_key_resolvers: {callables[path + \"::_sede_natural_key_resolvers\"]} <= 180')"` -> `module: 545 <= 1250; _natural_key_resolvers: 95 <= 180; _live_snapshot_natural_key_resolvers: 64 <= 180; _modelo_natural_key_resolvers: 24 <= 180; _sede_natural_key_resolvers: 24 <= 180`; exit `0`
