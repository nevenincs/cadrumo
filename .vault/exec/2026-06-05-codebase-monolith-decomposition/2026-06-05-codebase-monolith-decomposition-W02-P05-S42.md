---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S42'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W02.P05.S42 - extract modelo reconcile registrar

Scope: `src/aeat/entrypoints/cli/_modelo.py src/aeat/entrypoints/cli/_modelo_*.py`.

## Description

- Flatten `_modelo_reconcile_cli.py` so command functions live at module level.
- Keep `register_reconcile_commands` as a small dependency-injection and command-registration function.
- Preserve direct `app modelo reconcile` and `app modelo reconcile-from-justificante` command paths.
- Remove the stale oversized-registrar budget exception from the CLI size guard.

## Outcome

The reconcile command registrar no longer contains nested command bodies. Reconcile behavior still delegates to the application modelo reconciliation service, and the static command-size guard no longer needs a `register_reconcile_commands` exception.

## Notes

The refactor keeps natural-key and raw-ID parameters intact for the ADR-compatible operator surface.
