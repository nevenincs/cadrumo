---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S43'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W02.P05.S43 - verify modelo reconcile closure

Scope: `src/aeat/entrypoints/cli/tests/test_modelo* src/aeat/entrypoints/cli/tests/test_cli_module_size.py`.

## Description

- Run reconcile and reconcile-from-justificante behavior tests.
- Run the natural-key reconcile help test.
- Run lint for the flattened reconcile module and size guard.
- Run the global CLI module and command size guard.

## Outcome

Verification passed. Reconcile-focused tests reported 12 passing tests, ruff reported no issues, and `test_cli_module_size.py` reported 2 passing tests.

## Notes

The command-size guard now proves `register_reconcile_commands` fits the default command budget without a legacy exception.
