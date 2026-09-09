---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:104ccb6af426fbd9b21999cc238f8144fbcd0e96ddb64e8a09e042b4d44f1ddf'
step_id: 'S237'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the unused MODELO_CODE_CHOICE_ALL production constant and the development-only _MIGRATION_IN_PROGRESS classification that falsely clears every bare modelo axis; expose the live axes directly through the zero-target detector for owning-mechanism resolution.

## Scope

- `Shared CLI modelo choice authority`
- `closed-value-axis gate`
- `accepted closed-axis decision`
- `focused detector`
- `cadence reference`
- `and Step Record.`

## Changes

- `M` `src/cadrumo/entrypoints/cli/_common.py`
- `M` `src/cadrumo_harness/mcp/tests/test_closed_value_axis_gate.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync ruff check src/cadrumo/entrypoints/cli/_common.py src/cadrumo_harness/mcp/tests/test_closed_value_axis_gate.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q -n 0 -m "" --basetemp .tmp/pytest-s237 src/cadrumo_harness/mcp/tests/test_closed_value_axis_gate.py` -> `fail`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `fail`
