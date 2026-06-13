---
step_id: S336
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-30'
modified: '2026-05-30'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# codebase-solidification W03.P15.S336 — _validator.py clock enrollment

## Outcome

Enrolled 1 site at line 220 (datetime.now(tz=UTC)) in `src/aeat/domain/filing/_validator.py` to `_now()` from `aeat.core.time._clock`.

## Verification

`pytest src/aeat/test_clock_enrollment_inventory.py` passes.
