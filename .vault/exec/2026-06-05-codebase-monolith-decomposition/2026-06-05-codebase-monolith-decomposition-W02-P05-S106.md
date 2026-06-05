---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
step_id: 'S106'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W02.P05.S106 - verify ledger read extraction

Scope: `src/aeat/entrypoints/cli/tests/test_ledger* src/aeat/entrypoints/cli/tests/test_cli_module_size.py`.

## Description

- Run ruff over the ledger root, extracted read registrar, ledger verb-spine guard, and CLI size guard.
- Run focused ledger read/reporting tests covering verb roster, preflight, workbook export, list filters, view output, history/track lineage, and module-size budgets.

## Outcome

Verification passed. Ruff reported no issues, and the focused ledger read/reporting gate reported 34 passing tests.

## Notes

The legacy `_ledger.py` line budget remains ratcheted by `test_cli_module_size.py` after the extraction.
