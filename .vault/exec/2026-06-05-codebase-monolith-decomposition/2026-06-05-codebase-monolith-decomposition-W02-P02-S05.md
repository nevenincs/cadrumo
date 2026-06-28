---
tags: ['#exec', '#codebase-monolith-decomposition']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S05'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W02.P02.S05 - ledger business invoice verification

Scope: `src/aeat/entrypoints/cli/tests/test_business_invoice_verbs.py` and `src/aeat/entrypoints/cli/tests/test_cli_module_size.py`.

## Description

- Ran Ruff over the touched ledger CLI files and focused tests.
- Ran Python compileall over the touched ledger CLI modules.
- Ran the real-behavior payable and collectible invoice CLI tests.
- Ran the CLI module size guard and ratcheted `_ledger.py` from 4084 to 3550 lines.

## Outcome

Verification passed:

```text
uv run --no-sync ruff check src/aeat/entrypoints/cli/_ledger.py src/aeat/entrypoints/cli/_ledger_business_invoice_cli.py src/aeat/entrypoints/cli/tests/test_business_invoice_verbs.py src/aeat/entrypoints/cli/tests/test_cli_module_size.py
All checks passed.

uv run --no-sync python -m compileall -q src/aeat/entrypoints/cli/_ledger.py src/aeat/entrypoints/cli/_ledger_business_invoice_cli.py
passed

uv run --no-sync pytest -m integration src/aeat/entrypoints/cli/tests/test_business_invoice_verbs.py -q
5 passed

uv run --no-sync pytest src/aeat/entrypoints/cli/tests/test_cli_module_size.py -q
2 passed
```

The guard count uses Python `splitlines()`: `_ledger.py` is now 3550 lines and `_ledger_business_invoice_cli.py` is 557 lines.

## Notes

An initial budget ratchet used a PowerShell `Measure-Object -Line` count that omitted blank lines. The guard failure exposed the mismatch, and the budget was corrected to the guard's actual `splitlines()` count.
