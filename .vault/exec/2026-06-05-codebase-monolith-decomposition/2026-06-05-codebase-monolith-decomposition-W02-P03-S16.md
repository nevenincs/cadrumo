---
tags: ['#exec', '#codebase-monolith-decomposition']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S16'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W02.P03.S16 - modelo record verification

Scope: `src/aeat/entrypoints/cli/tests/test_modelo.py` and `src/aeat/entrypoints/cli/tests/test_cli_module_size.py`.

## Description

- Ran Ruff over the touched modelo CLI files and focused tests.
- Ran Python compileall over the touched modelo CLI modules.
- Ran focused integration tests for filing-record and verification-report rendering helper compatibility.
- Ran command help checks proving `filing-record` and `verification-report` remain mounted.
- Ran the CLI module size guard and ratcheted `_modelo.py` from 1881 to 1648 lines.

## Outcome

Verification passed:

```text
uv run --no-sync ruff check src/aeat/entrypoints/cli/_modelo.py src/aeat/entrypoints/cli/_modelo_records_cli.py src/aeat/entrypoints/cli/tests/test_modelo.py src/aeat/entrypoints/cli/tests/test_cli_module_size.py
All checks passed.

uv run --no-sync python -m compileall -q src/aeat/entrypoints/cli/_modelo.py src/aeat/entrypoints/cli/_modelo_records_cli.py
passed

uv run --no-sync pytest -m integration selected test_modelo.py filing-record and verification-report helper tests -q
5 passed

uv run --no-sync pytest src/aeat/entrypoints/cli/tests/test_cli_module_size.py -q
2 passed

ad hoc invoke_cached_cli help checks for app modelo filing-record and app modelo verification-report
both exit_code 0
```

The guard count uses Python `splitlines()`: `_modelo.py` is now 1648 lines and `_modelo_records_cli.py` is 316 lines.

## Notes

An initial ad hoc help check imported a non-existent helper module and failed before exercising the CLI. It was rerun through `aeat.tests.cli_runner.invoke_cached_cli` and passed.
