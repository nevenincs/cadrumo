---
tags:
  - '#exec'
  - '#binding-fold-in-carry-unification'
date: '2026-06-26'
modified: '2026-07-17'
body_hash: 'sha256:e311a6f119ff3957b90ab7ce25ae1e9c40764c2fa9fe90e517149180d25474b2'
step_id: 'S10'
related:
  - "[[2026-06-26-binding-fold-in-carry-unification-plan]]"
---

# vaultspec-code-reviewer: VERIFICATION GATE 1-BEFORE - run the #1 M303 refunded-period zero-carry, #7 M390 box 97 prior-pending, and #12 M390 box 662 applied-credit regression gates and record the baseline casilla values before any carry-reconciliation edit

## Scope

- `src/aeat/application/calculations/tests/test_modelo_303_refunded_period_carry.py`

## Description

- Verification gate 1 (before): run the #1 M303 refunded-period zero-carry, #7 M390 box-97 prior-pending, and #12 M390 box-662 applied-credit regression gates plus the pull-vs-calculate parity and cross-period clean-state surfaces, capturing the baseline before any carry-reconciliation edit.

## Outcome

- Baseline captured green at HEAD before the P03 edit: 66 tests passed across the carry gates, parity, cross-period clean-state, and the perceptor-count surface.

## Notes

- No code change in this gate Step; it records the pre-edit baseline the after-gate (S13) asserts against.
