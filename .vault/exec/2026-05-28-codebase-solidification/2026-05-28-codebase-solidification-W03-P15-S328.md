---
step_id: S328
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-30'
modified: '2026-05-30'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# codebase-solidification W03.P15.S328 — _local.py clock enrollment

## Outcome

Added `from ....core.time._clock import _now` import to
`src/aeat/adapters/outbound/storage/_local.py`.
Replaced 5 `datetime.now(UTC)` call-sites at lines 202, 269, 271, 337, 339
with `_now()`.

## Verification

`pytest src/aeat/test_clock_enrollment_inventory.py` passes.
`pytest src/aeat/adapters/persistence/storage/test_rotation.py` passes.
