---
tags:
  - '#exec'
  - '#arch-remediation-modelo-surface'
date: '2026-07-02'
modified: '2026-07-17'
step_id: 'S15'
related:
  - "[[2026-07-02-arch-remediation-modelo-surface-plan]]"
---

# Drive the caller-override rejection ladder guard code from the declared tier data rather than sequential inline guards

## Scope

- `src/aeat/application/modelo/_calculation_actions.py`

## Description

- Derive `BUCKET_AGGREGATION_LOCK_SOURCES` and `CALLER_OVERRIDABLE_CARRY_SOURCES` from the ladder in the calculation source policy, removing the hand-listed frozensets.

## Outcome

The two caller-override guard invocations consume ladder-derived sets; a source kind's lock-vs-carry disposition is declared once. Identical membership (8 lock, 3 carry). Commit `ddda33609`.

## Notes
