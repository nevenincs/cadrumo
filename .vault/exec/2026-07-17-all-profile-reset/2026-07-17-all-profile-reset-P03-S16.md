---
tags:
  - '#exec'
  - '#all-profile-reset'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S16'
related:
  - "[[2026-07-17-all-profile-reset-plan]]"
---

# Prove every reset phase boundary resumes honestly in a fresh child process

## Scope

- `src/cadrumo/application/tests/test_config_reset_recovery.py`

## Description

- Prove every durable reset phase boundary resumes honestly by crashing a real child process at each boundary (snapshotted, retention_approved, auth_clearing-after-effect, pointer_reconciling-after-effect, deleting-after-effect) and asserting the recorded journal phase.
- Prove the after-effect boundaries left the correct partial world: after `pointer_reconciling` the pointer file is already cleared; after `deleting` the bucket directory is already gone.
- Prove a fresh interpreter resumes each interrupted operation and rolls forward to COMPLETE, with the bucket deleted and pointer cleared, and the reloaded journal equal to the resumed result.
- Prove the auth-clearing crash boundary pauses `TARGET_STATE_CHANGED` on the first resume (the auth reset changed bucket content) and completes on a second resume — no phase leaves a half-deleted target and no premature completion record is written.

## Outcome

Real behavior throughout: real child processes crashed mid-operation via a hard exit code, real fresh-process resume, real encrypted storage — no mocks, stubs, or simulated crashes. This suite is the executable proof that a crash at any phase boundary resumes in a fresh process rather than leaving a half-deleted profile — the durability guarantee the ADR requires. Parametrized across all boundaries; 19 P03 tests green (this suite dominates the 105s runtime).

## Notes

Already checked in the plan without an execution record when I inherited P03; this record grounds the landed work (commit `60135859e2`) and re-verifies it green at HEAD. The crash harness uses a fixed non-zero exit code to distinguish a genuine mid-operation crash from an orderly exit.
