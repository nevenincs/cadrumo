---
tags: ['#exec', '#modelo-addressing-ux']
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S49'
related:
  - '[[2026-06-04-modelo-addressing-ux-plan]]'
---

# W03.P11.S49 work revision addressing

Scope:
- `src/aeat/entrypoints/cli/_modelo.py`
- `src/aeat/entrypoints/cli/test_modelo_work_natural_key.py`

## Description

- Classify `work revision` as natural-key plus revision-selector enrolled.
- Preserve exact calculation-revision id lookup for audit inspection.
- Cover `--select current` under a visible filing target.

## Outcome

Operators can inspect the current calculation revision under a visible filing target without copying its raw calculation-revision id.

## Notes

- Adjacent natural-key regression tests passed.
