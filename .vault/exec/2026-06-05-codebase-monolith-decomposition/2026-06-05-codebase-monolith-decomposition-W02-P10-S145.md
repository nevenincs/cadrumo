---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
step_id: 'S145'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W02.P10.S145 Budget Inventory Repair

Scope: `src/aeat/tests/test_codebase_size_budgets.py`; `src/aeat/application/modelo`; `src/aeat/entrypoints/cli/tests`.

## Description

- Removed stale legacy callable and module allowances for shrunken modelo compatibility modules.
- Made the tracked-file inventory ignore deleted tracked paths so concurrent renames do not raise `FileNotFoundError`.
- Replaced the retired cross-profile `switch` test surface with the root `unlock` equivalent.

## Outcome

- The hard size-budget test now reports actual budget offenders instead of failing on deleted tracked files.
- Verified by `src/aeat/tests/test_codebase_size_budgets.py`.

## Notes

- This step kept the guard strict for existing files; it only skips paths that no longer exist in the working tree.
