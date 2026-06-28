---
tags: ['#exec', '#modelo-addressing-ux']
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S15'
related:
  - '[[2026-06-04-modelo-addressing-ux-plan]]'
---

# W02.P03.S15 readable work list rows

Scope:
- `src/aeat/entrypoints/cli/_modelo.py`

## Description

- Render work-list rows with short work-unit ids.
- Include registry revision and current/filed calculation revision pointer columns in tabular output.

## Outcome

`modelo work list` now acts as a discovery surface for both visible filing targets and their calculation pointer state.

## Notes

- JSON list coverage asserts the pointer fields are populated after a real calculation.
