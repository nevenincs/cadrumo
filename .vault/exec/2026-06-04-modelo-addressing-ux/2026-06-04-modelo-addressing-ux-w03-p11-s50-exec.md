---
tags: ['#exec', '#modelo-addressing-ux']
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S50'
related:
  - '[[2026-06-04-modelo-addressing-ux-plan]]'
---

# W03.P11.S50 modelo reconcile addressing

Scope:
- `src/aeat/entrypoints/cli/_modelo.py`
- `src/aeat/entrypoints/cli/test_modelo_work_natural_key.py`

## Description

- Add natural target options to `modelo reconcile`.
- Resolve the work unit through the shared selector before calling the reconciliation service.
- Preserve positional exact work-unit id compatibility.

## Outcome

Common reconciliation can target the visible filing workspace without copied work-unit ids.

## Notes

- Help-surface regression verifies natural target options are advertised.
