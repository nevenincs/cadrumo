---
tags: ['#exec', '#modelo-work-revision-cli-decomposition']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S10'
related:
  - '[[2026-06-05-modelo-work-revision-cli-decomposition-plan]]'
---

# W03.P04.S10 Execution

Lowered the frozen `_modelo.py` size guard after extracting revision read and verify/file command bodies.

Outcome:
- `_modelo.py` frozen budget moved from 2070 to 1881.
- The current `_modelo.py` line count is 1881.
- Command-function size guard passes.

Passed:
- `uv run --no-sync ruff check src/aeat/entrypoints/cli/_modelo.py src/aeat/entrypoints/cli/_modelo_work_revision_cli.py src/aeat/entrypoints/cli/_modelo_work_verification_cli.py src/aeat/entrypoints/cli/test_cli_module_size.py`
- `uv run --no-sync pytest src/aeat/entrypoints/cli/test_cli_module_size.py::test_cli_command_functions_do_not_grow_past_complexity_budget -q`

Residual:
- `test_production_cli_modules_do_not_grow_into_new_monoliths` still fails only for unrelated existing modules `_app_live.py` and `_ledger.py`.
