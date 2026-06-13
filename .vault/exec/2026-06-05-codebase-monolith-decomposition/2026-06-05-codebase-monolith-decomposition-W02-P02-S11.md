---
tags: ['#exec', '#codebase-monolith-decomposition']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S11'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W02.P02.S11 - ledger inventory verification

Scope: `src/aeat/entrypoints/cli/tests/test_inventory_verbs.py` and `src/aeat/entrypoints/cli/tests/test_cli_module_size.py`.

## Description

- Ran Ruff over the touched ledger inventory CLI files and focused tests.
- Ran Python compileall over the touched ledger CLI modules.
- Ran the real-behavior inventory CLI tests.
- Ran the CLI module size guard and ratcheted `_ledger.py` from 3550 to 3314 lines.

## Outcome

Verification passed:

```text
uv run --no-sync ruff check src/aeat/entrypoints/cli/_ledger.py src/aeat/entrypoints/cli/_ledger_inventory_cli.py src/aeat/entrypoints/cli/tests/test_inventory_verbs.py src/aeat/entrypoints/cli/tests/test_cli_module_size.py
All checks passed.

uv run --no-sync python -m compileall -q src/aeat/entrypoints/cli/_ledger.py src/aeat/entrypoints/cli/_ledger_inventory_cli.py
passed

uv run --no-sync pytest -m integration src/aeat/entrypoints/cli/tests/test_inventory_verbs.py -q
4 passed

uv run --no-sync pytest src/aeat/entrypoints/cli/tests/test_cli_module_size.py -q
2 passed
```

The guard count uses Python `splitlines()`: `_ledger.py` is now 3314 lines and `_ledger_inventory_cli.py` is 277 lines.

## Notes

No fakes, mocks, skips, xfails, or monkeypatches were introduced.
