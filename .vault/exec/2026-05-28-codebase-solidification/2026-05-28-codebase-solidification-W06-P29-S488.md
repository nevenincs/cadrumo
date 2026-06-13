---
step_id: S488
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-31
modified: '2026-05-31'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# codebase-solidification W06.P29.S488

**Step**: migrate OracleEnvironment bare strings in application/registry/__init__.py:269-274,288-289 + entrypoints/cli/registry.py:184 to OracleEnvironment enum members.

## Outcome

- `_typed_oracle_environment` match arms now return `_OracleEnvironment.PRODUCTION`, `_OracleEnvironment.TEST_ENVIRONMENT`, `_OracleEnvironment.BOTH` (lines 269-274)
- `oracle_catalogue.register(..., environment="production")` → `environment=_OracleEnvironment.PRODUCTION` (lines 288-289)
- CLI default `= "production"` → `= _OracleEnvironment.PRODUCTION`; `OracleEnvironment` imported in `cli/registry.py`

## Files

- `src/aeat/application/registry/__init__.py`
- `src/aeat/entrypoints/cli/registry.py`

## Commit

5b45dd58c
