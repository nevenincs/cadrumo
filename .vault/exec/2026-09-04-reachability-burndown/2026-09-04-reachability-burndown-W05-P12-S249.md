---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:342b31fbfa9fc773ef7f08b9ccdd10970bfb6f1d54d1f0ce76045933a20b2a6f'
step_id: 'S249'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the Workspace refusal-union adjudication gate and remove its unproduced contract arms

## Scope

- `Narrow Workspace evidence facts and refusals to production-emitted shapes`
- `remove synthetic tests and stale presentation branches`
- `and prove the real producer-consumer boundary remains green`

## Changes

- `M` `src/cadrumo/application/modelo/workspace_models.py`
- `M` `src/cadrumo/application/modelo/workspace.py`
- `M` `src/cadrumo/application/modelo/tests/test_workspace_models.py`
- `M` `src/cadrumo/application/modelo/tests/test_workspace.py`
- `D` `src/cadrumo/application/modelo/tests/test_workspace_refusal_union_reachability.py`
- `M` `src/cadrumo/entrypoints/tui/modelo/view/models.py`
- `M` `src/cadrumo/entrypoints/tui/modelo/view/tests/test_workspace_view_models.py`
- `M` `dev/tests/test_workspace_field_population_gate.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync ruff check src/cadrumo/application/modelo/workspace_models.py src/cadrumo/application/modelo/workspace.py src/cadrumo/application/modelo/tests/test_workspace_models.py src/cadrumo/application/modelo/tests/test_workspace.py src/cadrumo/entrypoints/tui/modelo/view/models.py src/cadrumo/entrypoints/tui/modelo/view/tests/test_workspace_view_models.py dev/tests/test_workspace_field_population_gate.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/application/modelo/tests/test_workspace_models.py src/cadrumo/application/modelo/tests/test_workspace.py src/cadrumo/entrypoints/tui/modelo/view/tests/test_workspace_view_models.py dev/tests/test_workspace_field_population_gate.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `fail`
