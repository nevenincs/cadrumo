---
tags:
  - '#exec'
  - '#size-budget-refactor'
date: '2026-07-09'
modified: '2026-07-09'
step_id: 'S09'
related:
  - "[[2026-07-09-size-budget-refactor-plan]]"
---

# Run the deadlines test suite, ruff, pytest --collect-only, and test_codebase_size_budgets to confirm the callable is under budget with zero behavior drift

## Scope

- `src/aeat/domain/deadlines/tests/`

## Description

- Ran `ruff`, `ty`, and `pyright` on the touched file -- all clean.
- Ran the full `domain/deadlines` test suite plus every cross-package consumer test (user_profile corporate-tax/taxpayer-axes roundtrips, wizard taxpayer-axes roundtrip, CLI profile INCN/new-entity paths, the M200/M210 first-year e2e tests) -- 179+ tests, zero regressions.
- Confirmed `taxpayer_profile_from_mapping` no longer appears in the `test_codebase_size_budgets.py` offender list.

## Outcome

Zero behavior drift confirmed across the full cross-package consumer surface; the callable-size gate no longer flags `taxpayer_profile_from_mapping`.

## Notes

Landed by coder-perf (parallel P03 assignment per the plan's Parallelization section) as part of commit `ccd5e2057`; this record documents the completed Step for plan-closure purposes per `plan-closure-requires-exec-records`.
