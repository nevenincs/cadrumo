---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S41'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W02.P05.S41 - select modelo root closure command group

Scope: `src/aeat/entrypoints/cli/_modelo.py src/aeat/entrypoints/cli/tests`.

## Description

- Use the failing global size guard as exact discovery for the next modelo closure target.
- Inspect `_modelo_reconcile_cli.py` and reconcile behavior tests.
- Select the reconcile command registrar for flattening.

## Outcome

Selected `register_reconcile_commands` in `_modelo_reconcile_cli.py`. The registrar was 260 lines because it nested command definitions and rendering helpers, and the behavior was covered by reconcile tests and natural-key help tests.

## Notes

This selection was triggered while verifying the live extraction because the global command-size guard correctly caught the oversized modelo registrar.
