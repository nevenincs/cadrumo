---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:6092b2ef707be5ac3d33b3ae31c3585c0648f2b892eea553e103a2d49acd74f6'
step_id: 'S245'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the ownerless TUI operation-modal facade and correct production prose that advertises the nonexistent wrapper.

## Scope

- `Keep direct OperationModal and OperationController ownership`
- `preserve mounted modal behavior`
- `remeasure exact reachability`
- `update the cadence reference`
- `and write the Step Record.`

## Changes

- `D` `src/cadrumo/entrypoints/tui/operations/facade.py`
- `M` `src/cadrumo/entrypoints/tui/aeat_sync/models.py`
- `M` `src/cadrumo/entrypoints/tui/modelo/action/rename.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync ruff check src/cadrumo/entrypoints/tui/aeat_sync/models.py src/cadrumo/entrypoints/tui/modelo/action/rename.py src/cadrumo/entrypoints/tui/operations` -> `pass`
- `verify:` `uv run --no-sync pytest -q -n 0 -m "integration" src/cadrumo/entrypoints/tui/operations/tests/test_operation_modal_lifecycle.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `fail`

## Notes

The exact zero-target detector remains red on the live backlog. This Step reduced unreachable modules from 48 to 47; the remaining snapshot is 47 unreachable modules, 1 type-only module, 295 unused symbols, and 4 orphan tests.
