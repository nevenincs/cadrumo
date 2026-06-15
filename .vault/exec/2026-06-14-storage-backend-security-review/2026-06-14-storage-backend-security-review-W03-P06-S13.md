---
tags:
  - '#exec'
  - '#storage-backend-security-review'
date: '2026-06-14'
modified: '2026-06-15'
step_id: 'S13'
related:
  - "[[2026-06-14-storage-backend-security-review-plan]]"
---




# Re-read and re-validate the holder PID immediately before the stale-lock reclaim unlink

## Scope

- `src/aeat/adapters/persistence/storage/bucket/_lockfile.py`

## Description

- Add a re-read guard in `_reclaim_if_stale`: after judging the holder PID dead,
  re-read it immediately before the unlink and reclaim only when the record is
  byte-identical, so a peer's freshly re-created live lock is never deleted.

## Outcome

The stale-reclaim TOCTOU window is closed for the common case. 109 bucket tests
green. Committed in `382b5c08e`.

## Notes

A fully race-free reclaim needs inode-level operations (platform-specific); the
re-read guard is the proportionate fix the finding recommended for a MEDIUM item,
and the lock does not gate row writes so residual exposure is bounded. No
deterministic regression test added because the race is not reproducible without
internal injection (which the quality-gates rule discourages); existing lockfile
concurrency tests confirm no regression.
