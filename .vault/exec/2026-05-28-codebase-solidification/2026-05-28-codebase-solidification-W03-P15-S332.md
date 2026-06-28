---
step_id: S332
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-30'
modified: '2026-05-30'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# codebase-solidification W03.P15.S332 — _site_health_parsers.py clock enrollment

## Outcome

Enrolled 1 site at line 66 (_utcnow body) in `src/aeat/adapters/outbound/aeat/browser/_site_health_parsers.py` to `_now()` from `aeat.core.time._clock`.

## Verification

`pytest src/aeat/test_clock_enrollment_inventory.py` passes.
