---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S34'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W02.P05.S34 - verify ledger rule extraction

Scope: `src/aeat/entrypoints/cli/tests/test_ledger* src/aeat/entrypoints/cli/tests/test_cli_module_size.py`.

## Description

- Run the real-behavior ledger rule classification test suite.
- Run the CLI module size guard after the ledger root ratchet.
- Run output-language parity coverage to catch command-surface regressions.
- Run lint for the touched ledger CLI files and size guard.

## Outcome

Verification passed. `test_ledger_bulk_classify.py` reported 14 passing tests, `test_cli_module_size.py` reported 2 passing tests, `test_output_language_parity.py` reported 40 passing tests, and ruff reported no issues.

## Notes

The ledger root budget is ratcheted to the current extracted size of 2573 lines in the size guard.
