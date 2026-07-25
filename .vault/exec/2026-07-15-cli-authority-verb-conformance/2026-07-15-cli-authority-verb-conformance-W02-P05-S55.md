---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S55'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Expose target-scoped deletion assessment and verify reset operation ownership and fingerprint during deletion

## Scope

- `src/cadrumo/application/bucket_maintenance/_service.py`

## Description

- Add `assess_deletion` as the read-only, target-scoped assessment entry point returning an absent assessment for a missing bucket and a populated one carrying label, lifecycle status, deletion fingerprint, and retention floor for an existing bucket.
- Verify reset ownership inside the deletion path: when the command carries an operation id and expected fingerprint, resolve the journal through the reset repository and confirm the target is present, the fingerprint is owned, the retention decision is resolved, and a matching deleting marker exists.
- Recompute the deletion fingerprint under the held lock and refuse when it diverges from the caller's expected fingerprint, so a bucket mutated between assessment and deletion is not erased.
- Tolerate an already-absent target only when the command carries reset ownership, routing that tolerance through the same journal verification rather than a bare existence check.
- Carry the operation id and observed fingerprint onto the deletion result and its emitted event payload.
- Acquire deletion target locks in sorted UUID order through `deletion_target_locks`, skipping targets that do not exist rather than materialising a lockfile for them, and refusing a link-redirected target.

## Outcome

- Deletion is now operation-owned: an erase carrying reset ownership cannot proceed unless the durable journal independently confirms the target, its fingerprint, its resolved retention, and its deleting marker.
- A fingerprint recomputed under the lock is compared against the caller's expectation, closing the assess-then-mutate window.
- Absence tolerance is gated on journal proof rather than assumed, so a missing directory cannot be silently treated as a completed deletion by an unrelated caller.
- Assessment is genuinely read-only and does not open or mutate the bucket it describes.
- Landed in commit `11356b4792`; locking moved behind the application authority in `dc7bdccaf0`; the deletion path decomposed into named phase helpers in `f764cc53de`.

## Notes

- The work was already committed when this record was curated; the record documents the landed state verified against `HEAD` rather than a fresh edit.
- Lock acquisition sorts and de-duplicates its input set, so the ordering guarantee holds regardless of the caller's iteration order.
