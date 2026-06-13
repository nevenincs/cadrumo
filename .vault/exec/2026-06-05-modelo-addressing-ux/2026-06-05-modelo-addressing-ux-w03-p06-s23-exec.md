---
tags: ['#exec', '#modelo-addressing-ux']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S23'
related:
  - '[[2026-06-05-modelo-addressing-ux-plan]]'
---

# W03.P06.S23 lowered calculate command budget

Scope:
- `src/aeat/entrypoints/cli/test_cli_module_size.py`
- `src/aeat/entrypoints/cli/_modelo.py`
- `src/aeat/entrypoints/cli/_modelo_work_calculate_cli.py`

## Description

- Lowered the frozen `_modelo.py` module budget to the measured post-extraction size of `2321` lines.
- Verified there is no remaining legacy `("_modelo.py", "work_calculate")` command budget, because the command body no longer lives in `_modelo.py`.
- Measured current line counts: `_modelo.py` has `2321` lines, `_modelo_cli_support.py` has `556`, and `_modelo_work_calculate_cli.py` has `456`.

## Outcome

The calculate extraction budget guard is lowered for the modelo surface. The command-function guard passes; the broad module-size lane remains blocked by an unrelated `_app_live.py` budget failure.

## Verification

- `uv run --no-sync pytest src/aeat/entrypoints/cli/test_cli_module_size.py::test_cli_command_functions_do_not_grow_past_complexity_budget -q` passed.
- `uv run --no-sync pytest src/aeat/entrypoints/cli/test_architecture_boundaries.py src/aeat/entrypoints/cli/test_cli_module_size.py::test_cli_command_functions_do_not_grow_past_complexity_budget -q` passed with 6 tests.
- Broad `test_cli_module_size.py` remains expected to fail only because `_app_live.py` has `2262` lines against budget `2117`.
- Scoped counts show the touched modelo modules are within their current budgets.

## Notes

- This step did not change `_app_live.py` or its budget.
