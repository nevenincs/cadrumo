---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S54'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W03.P06.S54 - verify application modelo action decomposition

Scope: `src/aeat/application/modelo/tests`, `src/aeat/entrypoints/cli/tests/test_modelo*`.

## Description

- Run ruff over `_actions.py`, `_workflow_gate.py`, `_m210_rate.py`, and focused application-modelo tests.
- Run Modelo 210 convenio rate, action, and file-flow behavior tests.

## Outcome

Focused verification passed: ruff reported no findings and pytest reported 71 passing application-modelo tests.

## Notes

No public facade import changed.
