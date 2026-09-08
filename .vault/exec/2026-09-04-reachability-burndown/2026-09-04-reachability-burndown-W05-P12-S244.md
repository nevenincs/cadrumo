---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:d122a20754e88c938ca31f18c5478300afc9aa5f5923b5ca70ffc2a0b115baa4'
step_id: 'S244'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

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
