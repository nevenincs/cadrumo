---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S63'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Acquire target locks in sorted UUID order and persist every retention decision before mutation

## Scope

- `src/cadrumo/application/config_reset.py`

## Description

- Acquire the operation lock and the active-profile pointer transaction before target discovery, so the pointer cannot move while the target set is being computed.
- Route every target lock acquisition through the bucket-maintenance `deletion_target_locks` authority, which sorts and de-duplicates its input set, rather than opening lockfiles from the reset module directly.
- Pass the discovered target set to lock acquisition and pass the sorted tuple to preflight, so both the lock order and the recorded target order are deterministic by UUID.
- On resume, rebuild the lock set from the not-yet-deleted targets unioned with the current pointer bucket, sorted, and reacquire under the same authority and ordering.
- Compute each target's retention decision during preflight, before any auth clear, pointer reconciliation, or deletion runs.
- Persist the journal carrying every retention decision through `create_exclusive` before roll-forward begins, and persist the refreshed decision again after each auth-clear reassessment.
- Pause the operation with the retention-unresolved reason and the blocked target ids when any target's retention blocks erase without an approved override, returning before any mutation.

## Outcome

- Lock ordering is deadlock-free by construction: a single authority sorts and de-duplicates, and both the start and resume paths call it, so no second acquisition path with a divergent order exists.
- Every retention decision reaches durable storage before the mutation it authorizes, so a crash cannot leave a deletion whose retention basis was never recorded.
- A blocked retention floor pauses the operation with the blocking target ids named, rather than proceeding or silently downgrading the block.
- Lock acquisition skips targets that do not exist rather than materialising a lockfile for a dangling pointer identifier.
- Landed in commit `60135859e2`, with locking moved behind the application authority in `dc7bdccaf0`.

## Notes

- The work was already committed when this record was curated; the record documents the landed state verified against `HEAD` rather than a fresh edit.
- The retention override remains an explicit caller-supplied flag and reason pair; the orchestration never synthesises an override on the operator's behalf.
