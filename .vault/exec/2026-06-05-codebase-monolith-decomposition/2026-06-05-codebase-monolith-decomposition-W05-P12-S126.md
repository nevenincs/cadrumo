---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
step_id: 'S126'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W05.P12.S126 Ledger Action Test Split

Scope: `src/aeat/application/ledger/tests/test_actions.py`; `src/aeat/application/ledger/tests/*.py`.

## Description

- Split the oversized ledger action behavior test module into create, import/export, lifecycle, review, and update test modules.
- Moved shared secure-object repository setup and transaction fixtures into `_action_test_support.py`.
- Kept `test_actions.py` as a pointer module so the old surface remains discoverable without duplicating tests.

## Outcome

The ledger behavior tests now live in focused modules below the hard size budget while preserving real application imports and repository behavior.

## Notes

Verification passed for Ruff, compileall, 75 focused ledger behavior tests, and the 2-test hard codebase size-budget guard. No mocks, skips, xfails, or copied business logic were introduced.
