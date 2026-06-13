---
step_id: S331
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-30'
modified: '2026-05-30'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# codebase-solidification W03.P15.S331 — _clave_movil.py clock enrollment

## Outcome

Enrolled 7 sites at lines 387, 506, 1002, 1057, 1454, 1460, 1488 in `src/aeat/adapters/outbound/aeat/auth/_clave_movil.py` to `_now()` from `aeat.core.time._clock`.

## Verification

`pytest src/aeat/test_clock_enrollment_inventory.py` passes.
