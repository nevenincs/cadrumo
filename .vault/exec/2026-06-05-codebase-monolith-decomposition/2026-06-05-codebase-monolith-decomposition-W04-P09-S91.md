---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S91'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W04.P09.S91 Hard Size Guards

Scope: replace shrinking legacy size budgets with hard codebase-wide 1250-line and callable-complexity guards.

## Description

- Remove legacy module and callable allowlists from the codebase size-budget test.
- Replace git-tracked inventory with filesystem inventory under `src/aeat` so newly split files are covered before staging.
- Align CLI module size checks to the hard 1250-line module budget and 180-line command body budget.
- Preserve production-only callable checks while keeping test modules excluded from callable complexity enforcement.

## Outcome

Hard size guards are active with no legacy exceptions. Ruff passed for the size-budget tests, and the focused budget lane passed with 4 tests.

## Notes

No skips, xfails, fakes, mocks, or monkeypatches were introduced. The run-context invalid-id regression test was tightened to assert that rejected run ids create no new run artefacts even when other test fixtures have already populated the temporary directory.
