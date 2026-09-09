---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:df051fcec9f303fb1759fec2ae818e1a40ca9a733be4b7cca9568798fc1bf0f9'
step_id: 'S248'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

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
