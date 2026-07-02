---
tags:
  - '#exec'
  - '#arch-remediation-modelo-surface'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S16'
related:
  - "[[2026-07-02-arch-remediation-modelo-surface-plan]]"
---

# Add a conformance test binding the guard order to the declared precedence tier data so the two cannot diverge

## Scope

- `src/aeat/application/aggregation/tests/test_precedence_ladder_conformance.py`

## Description

- Add `test_precedence_ladder_conformance.py` binding the policy's derived sets to the ladder and pinning the ADR-frozen LOCK/CARRY memberships.

## Outcome

Guard sets and ladder declaration cannot silently diverge; a membership drift is caught as behavioural drift. Commit `ddda33609`.

## Notes
