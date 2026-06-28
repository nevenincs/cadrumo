---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S106'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W02.P05.S106 Ledger Read Verification

Scope: `src/aeat/entrypoints/cli/tests/test_ledger*`, `src/aeat/entrypoints/cli/tests/test_cli_module_size.py`.

## Description

- Ratchet `_ledger.py` module-size budget from 1946 to 1112 lines.
- Run ruff over `_ledger.py`, `_ledger_read_cli.py`, `test_cli_module_size.py`, and `test_cli_surface.py`.
- Verify command roster, list/review filters, preflight/check, workbook export, UX regression cluster, and CLI surface behavior.
- Repair `test_cli_surface.py` fixture data so update/classify keeps `taxable_base + iva_amount` equal to the changed gross amount.

## Outcome

All focused verification passed. `_ledger.py` is below the 1250-line threshold and guarded by the tighter 1112-line budget.

## Notes

Verification passed for the 26-test read/size set and the 52-test CLI surface/export/UX set. The only repair needed was non-tautological fixture data: the test now updates/classifies the 121.50 gross row with a matching 100.41 + 21.09 tax split.
