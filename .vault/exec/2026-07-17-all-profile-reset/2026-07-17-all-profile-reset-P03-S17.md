---
tags:
  - '#exec'
  - '#all-profile-reset'
date: '2026-07-17'
modified: '2026-07-17'
body_hash: 'sha256:61b9885f1f31ba0dd3a4507da34bf21ef002fb50bbbfa1e0abda5f77e686188e'
step_id: 'S17'
related:
  - "[[2026-07-17-all-profile-reset-plan]]"
---

# Prove sorted locking, writer pauses, reset exclusion, retention recheck, and renewed confirmation with real processes

## Scope

- `src/cadrumo/application/tests/test_config_reset_concurrency.py`

## Description

- Prove sorted target locking with real child processes: a lock holder on one bucket makes a competing reset wait for the lock timeout, and a concurrent application writer against another target is refused (fail-closed) while the reset is still blocked.
- Prove the blocked reset fails closed (BUSY exit) after the lock timeout, leaving the pointer bytes, both target fingerprints, and the profile label byte-identical, and writing no journal — nothing mutates on a contended lock.
- Prove fresh-process reset exclusion: a target under an active reset is excluded from a competing operation.
- Prove retention recheck and renewed confirmation on resume against real processes: a resume rechecks retention rather than inheriting the earlier decision, and confirmation is renewed rather than carried over.

## Outcome

Real behavior throughout: real child-process lock holders, real competing writer and reset processes, real elapsed-time assertions bounding the lock-timeout wait — no mocks or simulated locks. This suite is the executable proof that concurrent operations serialize in sorted order, contended writers pause rather than interleave, and a contended reset mutates nothing — the concurrency-safety half of the defect closure. 19 P03 tests green; ruff clean; collection clean.

## Notes

Already checked in the plan without an execution record when I inherited P03; this record grounds the landed work (commit `60135859e2`) and re-verifies it green at HEAD. The test bounds the reset's blocked-wait elapsed time to be at least the lock timeout, proving the wait is real rather than an immediate refusal.
