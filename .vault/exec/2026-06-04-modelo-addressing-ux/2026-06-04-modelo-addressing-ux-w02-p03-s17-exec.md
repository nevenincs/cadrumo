---
tags: ['#exec', '#modelo-addressing-ux']
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S17'
related:
  - '[[2026-06-04-modelo-addressing-ux-plan]]'
---

# W02.P03.S17 natural-key work revisions

Scope:
- `src/aeat/entrypoints/cli/_modelo.py`
- `src/aeat/entrypoints/cli/test_modelo_work_ux.py`

## Description

- Add natural filing target options to `modelo work revisions`.
- Preserve unfiltered listing when no exact id or natural target options are supplied.
- Resolve natural targets through the shared work selector before filtering calculation revisions.

## Outcome

`modelo work revisions` can now discover revisions under a visible filing target without requiring raw work-unit id input.

## Notes

- Focused tests cover both positional id compatibility and natural-key filtering.
