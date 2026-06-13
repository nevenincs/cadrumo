---
tags: ['#exec', '#modelo-addressing-ux']
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S45'
related:
  - '[[2026-06-04-modelo-addressing-ux-plan]]'
---

# W03.P10.S45 work discard addressing

Scope:
- `src/aeat/entrypoints/cli/_modelo.py`
- `src/aeat/entrypoints/cli/test_modelo_work_natural_key.py`

## Description

- Classify `work discard` as natural-key enrolled for active filing workspaces.
- Preserve the `--yes` confirmation gate.
- Cover natural-key discard against real persisted work-unit state.

## Outcome

Operators can explicitly abandon the active visible filing workspace without copying its raw work-unit id.

## Notes

- Adjacent natural-key regression tests passed.
