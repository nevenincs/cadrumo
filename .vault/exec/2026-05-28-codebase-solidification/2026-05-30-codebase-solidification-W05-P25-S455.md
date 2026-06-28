---
step_id: S455
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-30
modified: '2026-05-30'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# codebase-solidification W05.P25.S455

## Step

Fix regression: replace bare `os.environ["COLUMNS"]` with `_COLUMNS_ENV_VAR` at `cli/test_stdio.py:242,253,268` (constant already imported at line 37).

## Outcome

- Replaced 3 bare `os.environ["COLUMNS"]` references at lines 242, 253, 268 with `os.environ[_COLUMNS_ENV_VAR]`.
- `_COLUMNS_ENV_VAR` was already imported; no new import required.
- 19 tests in `test_stdio.py` pass.

## Files touched

- `src/aeat/entrypoints/cli/test_stdio.py`
