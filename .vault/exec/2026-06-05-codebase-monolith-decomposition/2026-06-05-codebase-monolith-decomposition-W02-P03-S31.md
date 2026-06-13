---
tags: ['#exec', '#codebase-monolith-decomposition']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S31'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W02.P03.S31 - residual modelo audit verification

Scope: `src/aeat/entrypoints/cli/tests/test_audit_verbs.py` and `src/aeat/entrypoints/cli/tests/test_cli_module_size.py`.

## Description

- Ran Ruff over the touched modelo CLI files and focused tests.
- Ran Python compileall over the touched modelo CLI files and size guard.
- Ran the modelo audit integration test module.
- Ran root CLI help checks for `app modelo audit` and every audit verb.
- Ran the CLI module and command size guard.
- Ratcheted `_modelo.py` from 1648 to 1434 lines.

## Outcome

Verification passed:

```text
uv run --no-sync ruff check src/aeat/entrypoints/cli/_modelo.py src/aeat/entrypoints/cli/_modelo_audit_cli.py src/aeat/entrypoints/cli/tests/test_audit_verbs.py src/aeat/entrypoints/cli/tests/test_cli_module_size.py
All checks passed.

uv run --no-sync python -m compileall -q src/aeat/entrypoints/cli/_modelo.py src/aeat/entrypoints/cli/_modelo_audit_cli.py src/aeat/entrypoints/cli/tests/test_cli_module_size.py
passed

uv run --no-sync pytest src/aeat/entrypoints/cli/tests/test_audit_verbs.py -m integration -q
11 passed

uv run --no-sync pytest src/aeat/entrypoints/cli/tests/test_cli_module_size.py -q
2 passed

ad hoc invoke_cached_cli help checks for app modelo audit show/check/export/replay
all exit_code 0
```

The guard count uses Python `splitlines()`: `_modelo.py` is now 1434 lines and `_modelo_audit_cli.py` is 237 lines.

## Notes

No residual failures in the focused modelo audit lane.
