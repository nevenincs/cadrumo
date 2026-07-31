---
step_id: S330
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-30'
modified: '2026-07-17'
body_hash: 'sha256:90e9a1064f2d3d5a25d40924fd43de1d78406f7cfb739d579bf7df38a0be897b'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# codebase-solidification W03.P15.S330 — _authenticator.py clock enrollment

## Outcome

Enrolled 3 sites at lines 550, 906, 1000 in `src/aeat/adapters/outbound/aeat/auth/_authenticator.py` to `_now()` from `aeat.core.time._clock`.

## Verification

`pytest src/aeat/test_clock_enrollment_inventory.py` passes.
