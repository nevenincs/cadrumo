---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:751a4b8ab3ab329476237b2f8724134e299375fdede5540969c063f4e099a155'
step_id: 'S245'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

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
