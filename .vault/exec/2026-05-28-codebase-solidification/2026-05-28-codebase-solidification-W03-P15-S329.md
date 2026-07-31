---
step_id: S329
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-30'
modified: '2026-07-17'
body_hash: 'sha256:9e8debfbf8e078bb77c4533e42b75490e75eda614e81687a32c833523d70f737'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# codebase-solidification W03.P15.S329 — _declarations.py clock enrollment

## Outcome

Enrolled 4 sites at lines 919, 1243, 1692, 1739 in `src/aeat/adapters/outbound/aeat/sede/_declarations.py` to `_now()` from `aeat.core.time._clock`.

## Verification

`pytest src/aeat/test_clock_enrollment_inventory.py` passes.
