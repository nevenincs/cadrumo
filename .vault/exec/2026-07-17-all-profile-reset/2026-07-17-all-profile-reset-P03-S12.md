---
tags:
  - '#exec'
  - '#all-profile-reset'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S12'
related:
  - "[[2026-07-17-all-profile-reset-plan]]"
---

# Invoke strong profile logout for the active reset target and reconcile dangling pointers through the core authority

## Scope

- `src/cadrumo/application/config_reset.py`

## Description

- Strongly logout the active reset target (`_reconcile_pointer`): when the active-pointer bucket is a member of the target set, call `logout_active_profile` (close and zeroise the session, release the lockfile, clear the pointer) between the `POINTER_RECONCILING` and `POINTER_RECONCILED` phases, so no target is deleted while it is the live active bucket.
- Reconcile a dangling pointer through the core authority: on resume, `_reconcile_pointer_snapshot_for_resume` re-reads the pointer under the pointer transaction and, when it changed, adds the newly-pointed bucket as a target or pauses (`POINTER_CHANGED`) for renewed confirmation rather than proceeding on a stale snapshot.
- Capture the pointer snapshot (`_capture_pointer_snapshot`) as presence + bucket id + content SHA-256 so pointer drift is detectable, and clear it as part of deleting the bucket it names.

## Outcome

This is the phase that closes the "delete active bucket leaves a dangling pointer" defect end to end: the active target is strongly logged out (pointer cleared) before its bucket is erased, and a pointer that changed between snapshot and resume is reconciled or paused, never stranded. Proven by the P03.S15 test (dangling pointer discovered and the pointer file gone after reset) and the P03.S16 `pointer_reconciling_after_effect` crash boundary (pointer already cleared, resume rolls forward). 19 P03 tests green.

## Notes

Landed in commit `60135859e2`; re-verified at HEAD. `logout_active_profile` and the pointer transaction are the canonical `application/user_profile` authorities consumed through the package facade — no second pointer writer is introduced (composition-service-no-parallel-write-path).
