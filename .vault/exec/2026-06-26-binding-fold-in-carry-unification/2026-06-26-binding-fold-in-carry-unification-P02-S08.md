---
tags:
  - '#exec'
  - '#binding-fold-in-carry-unification'
date: '2026-06-26'
modified: '2026-07-17'
step_id: 'S08'
related:
  - "[[2026-06-26-binding-fold-in-carry-unification-plan]]"
---

# vaultspec-code-reviewer: VERIFICATION GATE 5b - run full-calc, cross-period-continuity, and oracle suites after the fold-helper collapse and assert NO casilla value shifts with M130 and M353 shapes byte-identical

## Scope

- `src/aeat/application/calculations/tests/test_pull_path_calculate_path_casilla_parity.py`

## Description

- Verification gate 5b: run the full-calc, cross-period-continuity, and oracle surfaces after the fold-helper collapse (S06 plus S07) and assert NO casilla value shifts, with the M130 prior_pagos and M353 per_grupo_member shapes preserved.

## Outcome

- The full registry plus calculations suites passed (3253 tests), unchanged from the S05 baseline; the M130 casilla-05 carry, M390 FIFO, M303 refunded-period, and pull-vs-calculate parity gates passed; collect-only clean. No casilla value shifted across S06 or S07.

## Notes

- No code change in this gate Step; it is a verification barrier. Both fold collapses are value-preserving by construction (the gather and the copy/sum arithmetic are byte-for-byte the prior logic, single-sourced), so the suite parity confirms the dedup introduced no shift.
