---
tags: ['#exec', '#codebase-monolith-decomposition']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S28'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W02.P03.S28 - residual live verify verification

Scope: `src/aeat/entrypoints/cli/tests/test_live_read_subgroups.py` and `src/aeat/entrypoints/cli/tests/test_cli_module_size.py`.

## Description

- Ran Ruff over the touched live CLI files and focused tests.
- Ran Python compileall over the touched live CLI files and size guard.
- Ran the live read subgroup integration test module.
- Ran root CLI help checks for `app live verify` and every verify verb.
- Ran the CLI module and command size guard.
- Ratcheted `_app_live.py` from 1882 to 1580 lines.

## Outcome

Verification passed:

```text
uv run --no-sync ruff check src/aeat/entrypoints/cli/_app_live.py src/aeat/entrypoints/cli/_app_live_verify_cli.py src/aeat/entrypoints/cli/tests/test_live_read_subgroups.py src/aeat/entrypoints/cli/tests/test_cli_module_size.py
All checks passed.

uv run --no-sync python -m compileall -q src/aeat/entrypoints/cli/_app_live.py src/aeat/entrypoints/cli/_app_live_verify_cli.py src/aeat/entrypoints/cli/tests/test_cli_module_size.py
passed

uv run --no-sync pytest src/aeat/entrypoints/cli/tests/test_live_read_subgroups.py -m integration -q
25 passed

uv run --no-sync pytest src/aeat/entrypoints/cli/tests/test_cli_module_size.py -q
2 passed

ad hoc invoke_cached_cli help checks for app live verify list/view/latest/nif-iva/tgvi
all exit_code 0
```

The guard count uses Python `splitlines()`: `_app_live.py` is now 1580 lines and `_app_live_verify_cli.py` is 336 lines.

## Notes

No residual failures in the focused live verification lane.
