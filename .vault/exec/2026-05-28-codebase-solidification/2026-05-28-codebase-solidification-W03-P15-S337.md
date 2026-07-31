---
step_id: S337
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-30'
modified: '2026-07-17'
body_hash: 'sha256:69154af7049c606e35cfba21a5b6581beb4e56b1b85a3e6b6c4f8d808e00a135'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# codebase-solidification W03.P15.S337 — _context.py clock enrollment

## Outcome

Enrolled 2 sites at lines 128, 296 (intra-core) in `src/aeat/core/observability/_context.py` to `_now()` from `aeat.core.time._clock`.

## Verification

`pytest src/aeat/test_clock_enrollment_inventory.py` passes.
