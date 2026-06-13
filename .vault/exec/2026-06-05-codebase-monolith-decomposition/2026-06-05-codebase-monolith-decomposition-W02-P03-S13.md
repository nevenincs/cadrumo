---
tags: ['#exec', '#codebase-monolith-decomposition']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S13'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W02.P03.S13 - live notifications verification

Scope: `src/aeat/entrypoints/cli/tests/test_live_notifications_verbs.py`, `src/aeat/entrypoints/cli/tests/test_registry_cli.py`, and `src/aeat/entrypoints/cli/tests/test_cli_module_size.py`.

## Description

- Ran Ruff over the touched live CLI files and focused tests.
- Ran Python compileall over the touched live CLI modules.
- Ran the real-behavior live notifications CLI tests.
- Ran the registry help test proving the nested command remains mounted.
- Ran the CLI module size guard and ratcheted `_app_live.py` from 2061 to 1882 lines.

## Outcome

Verification passed:

```text
uv run --no-sync ruff check src/aeat/entrypoints/cli/_app_live.py src/aeat/entrypoints/cli/_app_live_notifications_cli.py src/aeat/entrypoints/cli/tests/test_live_notifications_verbs.py src/aeat/entrypoints/cli/tests/test_registry_cli.py src/aeat/entrypoints/cli/tests/test_cli_module_size.py
All checks passed.

uv run --no-sync python -m compileall -q src/aeat/entrypoints/cli/_app_live.py src/aeat/entrypoints/cli/_app_live_notifications_cli.py
passed

uv run --no-sync pytest -m integration src/aeat/entrypoints/cli/tests/test_live_notifications_verbs.py src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_notifications_latest_cli_help_resolves -q
3 passed, 1 warning

uv run --no-sync pytest src/aeat/entrypoints/cli/tests/test_cli_module_size.py -q
2 passed
```

The guard count uses Python `splitlines()`: `_app_live.py` is now 1882 lines and `_app_live_notifications_cli.py` is 204 lines.

## Notes

The registry help test emits an existing Click 9 deprecation warning from the CLI bootstrap. It does not affect this slice.
