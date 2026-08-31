---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:f9e56e69a4ea85350495b6d9f3b3c4faa564bf0971e2c2ccbcb3d681d191fb49'
step_id: 'S214'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
# `ci-lane-deconflation` execution record: `P05.S214`

## Scope

- `P05.S214`

## Changes

- `M` `src/cadrumo/domain/iva/components.py`
- `A` `src/cadrumo/domain/iva/_component_rows.py`
- `M` `.vault/plan/2026-08-05-ci-lane-deconflation-plan.md`
- `A` `.vault/exec/2026-08-05-ci-lane-deconflation/2026-08-05-ci-lane-deconflation-P05-S214.md`

## Notes

- `uv run --no-sync ruff check src/cadrumo/domain/iva/components.py src/cadrumo/domain/iva/_component_rows.py` emitted `All checks passed!` (exit 0); `uv run --no-sync ruff format --check src/cadrumo/domain/iva/components.py src/cadrumo/domain/iva/_component_rows.py` emitted `2 files already formatted` (exit 0).
- `uv run --no-sync python -c "from cadrumo.domain.iva.components import IVA_CATEGORY_COMPONENTS; print(f'component rows: {len(IVA_CATEGORY_COMPONENTS)}')"` emitted `component rows: 42` (exit 0).
- `uv run --no-sync pytest --collect-only -q src/cadrumo/domain/iva/tests/test_component_expectations.py src/cadrumo/domain/iva/tests/test_intra_community_identification_axis.py` collected 102 tests (exit 0); the matching focused run emitted `102 passed in 5.63s` (exit 0).
- `uv run --no-sync python -c "from dev.audit.size_budget import measure_module_lines; measured=measure_module_lines(); key='src/cadrumo/domain/iva/components.py'; print(f'{key}: {measured[key]} lines; default module budget 1250; exit 0')"` emitted `src/cadrumo/domain/iva/components.py: 550 lines; default module budget 1250; exit 0`; no policy or baseline changed.
- Before S214 plan mutation, `HEAD` and worktree plan blobs were both `e300293d6bfea546a22487fcfd73b5d40e9ffa3b`; the shared default index was separately pinned at `dafa57578eb05350b52c0aac54923edec1427506`. The isolated commit uses a fresh HEAD index and stages only the S214 row and generated body hash, preserving the peer's default-index hunk.
