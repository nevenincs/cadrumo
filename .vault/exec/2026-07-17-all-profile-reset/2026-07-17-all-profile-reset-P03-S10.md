---
tags:
  - '#exec'
  - '#all-profile-reset'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S10'
related:
  - "[[2026-07-17-all-profile-reset-plan]]"
---




# Acquire target locks in sorted UUID order and persist every retention decision before mutation

## Scope

- `src/cadrumo/application/config_reset.py`

## Description

- Acquire every target's exclusive bucket lock in sorted UUID order through `BucketMaintenanceService.deletion_target_locks(bucket_ids=target_ids)`, both at start and on resume, so two concurrent operations cannot deadlock.
- Run the retention preflight (`_initial_preflight`) under those locks: assess every target, record a `ConfigResetRetentionDecision` per target, and persist the whole journal (`create_exclusive`) BEFORE any auth, pointer, or bucket mutation begins.
- Pause the operation (status PAUSED, `RETENTION_UNRESOLVED`, blocked target ids) when any target's retention floor blocks erase without an approved override, refusing before mutation rather than after.

## Outcome

Every retention decision is durable before the first irreversible action, so a crash between preflight and deletion resumes from a recorded decision rather than re-guessing. Sorted-order locking is proven under real child-process contention. Proven by the P03.S17 sorted-lock concurrency test (a blocked reset waits the lock timeout and fails closed, mutating nothing) and the P03.S15 retention-preflight-pauses-before-mutation test. 19 P03 tests green.

## Notes

Landed in commit `60135859e2`; re-verified at HEAD. Bulk reset does not copy private retention logic — it consumes the same public `assess_deletion` the single-bucket delete path uses, satisfying the ADR constraint that bulk reset cannot re-implement retention or switch the global pointer merely to reach a bucket.
