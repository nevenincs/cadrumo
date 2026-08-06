---
tags: ['#exec', '#modelo-addressing-ux']
date: '2026-06-04'
modified: '2026-07-17'
body_hash: 'sha256:1f7f32ca06416be2aec60e8d904ad953f8d0aaa4a1e187307f25d44bd067c459'
step_id: 'S20'
related:
  - '[[2026-06-04-modelo-addressing-ux-plan]]'
---

# W02.P04.S20 natural-key work calculate

Scope:
- `src/aeat/entrypoints/cli/_modelo.py`
- `src/aeat/entrypoints/cli/test_modelo_work_ux.py`

## Description

- Confirm `modelo work calculate` resolves either an exact work-unit id or a natural modelo/year/period target through the shared selector.
- Cover natural-key calculation with a real modelo work unit and persisted draft revision.

## Outcome

Operators can calculate a visible filing target without copying the raw `work_unit_id`.

## Notes

- Focused CLI lifecycle tests passed.
