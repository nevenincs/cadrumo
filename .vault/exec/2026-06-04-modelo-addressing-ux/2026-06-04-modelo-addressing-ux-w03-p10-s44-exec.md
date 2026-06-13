---
tags: ['#exec', '#modelo-addressing-ux']
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S44'
related:
  - '[[2026-06-04-modelo-addressing-ux-plan]]'
---

# W03.P10.S44 work rename addressing

Scope:
- `src/aeat/entrypoints/cli/_modelo.py`
- `src/aeat/entrypoints/cli/test_modelo_work_natural_key.py`

## Description

- Classify `work rename` as natural-key enrolled for active filing workspaces.
- Confirm exact id remains accepted through the shared selector.
- Cover natural-key rename against real persisted work-unit state.

## Outcome

Operators can rename the active visible filing workspace without copying its raw work-unit id.

## Notes

- Adjacent natural-key regression tests passed.
