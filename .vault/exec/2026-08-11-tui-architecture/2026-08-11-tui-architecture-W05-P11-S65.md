---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:31065ebdad3d4fdc118f802911e536f006ad14396695f88d6cdf31c9232e7457'
step_id: 'S65'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Expose a narrow operation-presentation facade that accepts only public operation contracts and exports neither Textual internals nor application-private operation types as backend contracts

## Scope

- `src/cadrumo/entrypoints/tui/operations/__init__.py`

## Changes

- `A` `src/cadrumo/entrypoints/tui/operations/__init__.py`
- `A` `src/cadrumo/entrypoints/tui/operations/facade.py`

## Notes

The facade landed as `facade.py`, not inside `__init__.py`: the project's
import-boundary rule requires every package `__init__.py` to stay inert
(empty `__all__`, no re-exports), so the narrow presentation door is a
sibling public defining module instead. It exposes a calling convention
(`present_operation_modal`, `is_detached_outcome`) rather than re-exporting
sibling symbols, keeping it a real facade rather than a re-export module.
