---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:fe9ff9c4a650561a5027406251269306c773a7970f8e71806728fa96f44e30db'
step_id: 'S244'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Withdraw and delete the unreachable generic TUI error and log component slice now superseded by the live operation modal projection.

## Scope

- `Remove the three production modules and self-only tests`
- `retain the live operation-specific renderer and unrelated component behavior`
- `amend contradicted TUI architecture prose`
- `remeasure exact reachability`
- `update the cadence reference`
- `and write the Step Record.`

## Changes

- `D` `src/cadrumo/entrypoints/tui/components/_safe_text.py`
- `D` `src/cadrumo/entrypoints/tui/components/errors.py`
- `D` `src/cadrumo/entrypoints/tui/components/logs.py`
- `D` `src/cadrumo/entrypoints/tui/components/tests/test_errors.py`
- `D` `src/cadrumo/entrypoints/tui/components/tests/test_logs.py`
- `M` `src/cadrumo/entrypoints/tui/components/tests/test_feedback.py`
- `M` `src/cadrumo/entrypoints/tui/components/tests/test_component_boundary.py`
- `M` `.vault/adr/2026-08-11-tui-architecture-adr.md`
- `M` `.vault/reference/2026-09-02-unreachable-capability-disconnected-capability-inventory-reference.md`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync ruff check src/cadrumo/entrypoints/tui/components src/cadrumo/entrypoints/tui/operations` -> `pass`
- `verify:` `uv run --no-sync pytest -q -n 0 src/cadrumo/entrypoints/tui/components/tests/test_feedback.py src/cadrumo/entrypoints/tui/components/tests/test_component_boundary.py src/cadrumo/entrypoints/tui/operations/tests/test_operation_modal_lifecycle.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q -n 0 -m "integration" src/cadrumo/entrypoints/tui/components/tests/test_feedback.py src/cadrumo/entrypoints/tui/components/tests/test_component_boundary.py src/cadrumo/entrypoints/tui/operations/tests/test_operation_modal_lifecycle.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `fail`

## Notes

The exact zero-target detector remains red on the live backlog, but this coherent slice reduced unreachable modules from 51 to 48. The remaining snapshot is 48 unreachable modules, 1 type-only module, 295 unused symbols, and 4 orphan tests.
