---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S146'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W02.P10.S146 Config and Size-Budget Verification

Scope: verify residual config callable splits and hard size-budget inventory no longer fail on stale paths or config registrar callables.

## Description

- Verified changed config custody and censo modules with Ruff.
- Verified focused config CLI behavior across custody, profile censo, auth, repair, apoderado, Google sync, and bucket-history tests.
- Verified hard size-budget checks pass across tracked Python modules and production callables.
- Verified the plan with `vaultspec-core vault plan check`.

## Outcome

Residual config registrar splits are complete and the hard size-budget gate passes for the current tracked worktree.

## Notes

Passing checks: 57 focused config CLI tests; 17 application censo service tests; 11 profile censo CLI tests; `src/aeat/tests/test_codebase_size_budgets.py`; and plan check with only the known inserted-step monotonicity warning.
