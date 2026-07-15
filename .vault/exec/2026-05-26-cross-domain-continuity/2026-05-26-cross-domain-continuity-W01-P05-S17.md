---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-10'
modified: '2026-07-10'
step_id: 'S17'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# update _decimal_value to accept lowercase canonical strings in addition to the Python form

## Scope

- `src/aeat/application/modelo/_profile_binding.py`

## Description

- Reconciled the lowercase boolean coercion change to the Wave-1 commit review.
- Confirmed `17a0c3023` supplied the reviewed implementation.
- Added this per-step execution record without changing production sources.

## Outcome

The 2026-05-27 review accepted the implementation. This record restores the one-Step, one-record traceability edge.

## Notes

Historical evidence predates the current per-step record convention.
