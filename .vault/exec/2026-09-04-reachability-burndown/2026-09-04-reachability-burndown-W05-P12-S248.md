---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:7afcecf455825eb56c428f50478b2cee18177a8adc2fdd7489949af92a9ee01f'
step_id: 'S248'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Delete the unused ModeloWorkspaceVersionHeader pre-dispatch DTO and export because no parser or product boundary consumes it.

## Scope

- `Retain the live request and refusal version handling`
- `run focused workspace model gates`
- `remeasure exact reachability`
- `update the cadence reference`
- `and write the Step Record.`

## Changes

- `M` `src/cadrumo/application/modelo/workspace_models.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync ruff check src/cadrumo/application/modelo/workspace_models.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q -n 0 -m "" src/cadrumo/application/modelo/tests/test_workspace_models.py src/cadrumo/application/modelo/tests/test_workspace_refusal_union_reachability.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `fail`

## Notes

The exact zero-target detector remains red on the live backlog. This Step reduced exact unused symbols from 291 to 290 while retaining 34 unreachable modules, 1 type-only module, and 0 orphan tests.
