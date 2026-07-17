---
tags:
  - '#exec'
  - '#all-profile-reset'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S13'
related:
  - "[[2026-07-17-all-profile-reset-plan]]"
---




# Persist deleting ownership before deletion and completion after each irreversible transition

## Scope

- `src/cadrumo/application/config_reset.py`

## Description

- Persist deleting ownership before each irreversible erase (`_delete_targets`): record the `DELETING` phase with a `ConfigResetDeletionMarker` (operation id, bucket id, fingerprint, marked-at) and save the journal BEFORE calling `BucketMaintenanceService.delete`.
- Pass that operation id and expected fingerprint into the delete command, so the bucket-deletion authority accepts the erase only when the journal owns it (the P01 ownership check).
- Record completion after each irreversible transition: set the `DELETED` phase and `completed_at` and save the journal after the delete returns; an already-absent target transitions straight to `DELETED` with its completion timestamp.
- Write the final `ConfigResetSummary` (reconciled deleted / already-absent / override counts) and mark the operation COMPLETE only after every target is deleted.

## Outcome

The journal always records the intent to delete before the deletion happens and records completion after, so on resume an absent target counts as already completed only when the journal proves ownership — generic absence stays an error. This is the roll-forward-not-rollback discipline the ADR mandates after the first irreversible deletion. Proven by the P03.S16 `deleting_after_effect` crash boundary (bucket already gone, journal shows the deleting marker, resume completes idempotently) and the P01.S05 journal-proven-absence test. 19 P03 tests green.

## Notes

Landed in commit `60135859e2`; re-verified at HEAD. The marker's operation id and fingerprint are validated against the journal by `verify_deletion_ownership`, so a forged or stale marker cannot authorise a deletion.
