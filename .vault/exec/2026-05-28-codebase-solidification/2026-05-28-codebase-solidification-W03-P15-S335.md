---
step_id: S335
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-30'
modified: '2026-05-30'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# codebase-solidification W03.P15.S335 — _complementaria_repository.py clock enrollment

## Outcome

Enrolled 1 site at line 100 in `src/aeat/domain/filing/_complementaria_repository.py` to `_now()` from `aeat.core.time._clock`.

## Verification

`pytest src/aeat/test_clock_enrollment_inventory.py` passes.
