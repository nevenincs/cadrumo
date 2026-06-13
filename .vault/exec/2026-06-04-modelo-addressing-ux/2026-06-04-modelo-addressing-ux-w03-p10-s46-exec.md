---
tags: ['#exec', '#modelo-addressing-ux']
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S46'
related:
  - '[[2026-06-04-modelo-addressing-ux-plan]]'
---

# W03.P10.S46 work history addressing

Scope:
- `src/aeat/entrypoints/cli/_modelo.py`
- `src/aeat/entrypoints/cli/test_modelo_work_natural_key.py`

## Description

- Classify `work history` as natural-key enrolled for active filing workspace history.
- Preserve exact work-unit id lookup for audit replay.
- Cover natural-key history rendering after create/rename/calculate events.

## Outcome

Operators can inspect a visible filing target's lifecycle history without copying its raw work-unit id.

## Notes

- Adjacent natural-key regression tests passed.
