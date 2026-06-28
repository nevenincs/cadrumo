---
step_id: S333
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-30'
modified: '2026-05-30'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# codebase-solidification W03.P15.S333 — _rotation.py clock enrollment

## Outcome

Enrolled 2 sites at lines 333, 349 in `src/aeat/adapters/persistence/storage/_rotation.py` to `_now()` from `aeat.core.time._clock`.

## Verification

`pytest src/aeat/test_clock_enrollment_inventory.py` passes.
