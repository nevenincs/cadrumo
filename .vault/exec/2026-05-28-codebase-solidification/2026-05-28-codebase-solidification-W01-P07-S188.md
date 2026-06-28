---
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
step_id: 'S188'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# codebase-solidification W01.P07.S188

Add real-behaviour tests verifying `_COLUMNS_ENV_VAR` identity and env-mutation contract.

- Modified: `src/aeat/entrypoints/cli/test_stdio.py`

## Description

Extended the import block to include `_COLUMNS_ENV_VAR`. Added three tests:

- `test_columns_env_var_constant_value`: asserts `_COLUMNS_ENV_VAR == "COLUMNS"` to lock the string value against future drift.
- `test_columns_env_var_used_for_env_write`: exercises a `--help` invocation with a narrow terminal (80 cols) and verifies `os.environ[_COLUMNS_ENV_VAR]` is raised to the floor, confirming the write path uses the constant.
- `test_columns_env_var_used_for_env_read`: sets the env slot above the floor and confirms the function leaves it unchanged, confirming the read path also uses the constant.

## Tests

14/14 tests pass: `uv run --no-sync pytest src/aeat/entrypoints/cli/test_stdio.py -xvs --cache-clear`. Three new tests cover S188 contract; eleven pre-existing tests remain green.
