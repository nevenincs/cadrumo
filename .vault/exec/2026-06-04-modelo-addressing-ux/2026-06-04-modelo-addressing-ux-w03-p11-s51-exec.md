---
tags: ['#exec', '#modelo-addressing-ux']
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S51'
related:
  - '[[2026-06-04-modelo-addressing-ux-plan]]'
---

# W03.P11.S51 reconcile-from-justificante addressing

Scope:
- `src/aeat/entrypoints/cli/_modelo.py`
- `src/aeat/entrypoints/cli/test_modelo_work_natural_key.py`

## Description

- Add natural target options to `modelo reconcile-from-justificante`.
- Resolve the work unit through the shared selector before calling the reconciliation service.
- Preserve optional positional exact work-unit id compatibility after the justificante path.

## Outcome

The justificante-first reconciliation shortcut now supports visible filing target addressing.

## Notes

- Help-surface regression verifies natural target options are advertised.
