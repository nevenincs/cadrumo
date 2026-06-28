---
tags: ['#exec', '#codebase-monolith-decomposition']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S25'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W02.P03.S25 - residual ledger ratios verification

Scope: `src/aeat/entrypoints/cli/tests/test_ratios_verbs.py` and `src/aeat/entrypoints/cli/tests/test_cli_module_size.py`.

## Description

- Ran Ruff over the touched ledger CLI files and focused tests.
- Ran Python compileall over the touched ledger CLI files and size guard.
- Ran the ratios integration test module.
- Ran root CLI help checks for `app ledger ratios` and every ratios verb.
- Ran the CLI module and command size guard.
- Ratcheted `_ledger.py` from 3314 to 2890 lines.

## Outcome

Verification passed:

```text
uv run --no-sync ruff check src/aeat/entrypoints/cli/_ledger.py src/aeat/entrypoints/cli/_ledger_ratios_cli.py src/aeat/entrypoints/cli/tests/test_ratios_verbs.py src/aeat/entrypoints/cli/tests/test_cli_module_size.py
All checks passed.

uv run --no-sync python -m compileall -q src/aeat/entrypoints/cli/_ledger.py src/aeat/entrypoints/cli/_ledger_ratios_cli.py src/aeat/entrypoints/cli/tests/test_cli_module_size.py
passed

uv run --no-sync pytest src/aeat/entrypoints/cli/tests/test_ratios_verbs.py -m integration -q
14 passed

uv run --no-sync pytest src/aeat/entrypoints/cli/tests/test_cli_module_size.py -q
2 passed

ad hoc invoke_cached_cli help checks for app ledger ratios list/set/unset/eligible/validate
all exit_code 0 and verb help exposes --output-language
```

The guard count uses Python `splitlines()`: `_ledger.py` is now 2890 lines and `_ledger_ratios_cli.py` is 426 lines.

## Notes

The size guard also needed `_config/_google.py` budget adjusted from 1399 to 1400 because that file already has an unrelated one-line worktree change adding `translated_message` to a Google sync refusal.
