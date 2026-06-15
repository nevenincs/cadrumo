---
tags:
  - '#exec'
  - '#storage-backend-security-review'
date: '2026-06-14'
modified: '2026-06-15'
step_id: 'S14'
related:
  - "[[2026-06-14-storage-backend-security-review-plan]]"
---




# Dispose the cached engine when a bucket DB is hard-deleted so a recreated file does not reuse stale connections

## Scope

- `src/aeat/adapters/persistence/storage/sql/engine.py`

## Description

- Dispose the cached SQLAlchemy engine pool (then `gc.collect`) at the start of
  `remove_profile_bucket_directory`, before the crash-safe rename.

## Outcome

The bucket's SQLite file handle is released before removal, so the Windows
rename-refusal fallback is avoided and a cached engine can no longer serve stale
connections to a deleted-then-recreated bucket DB. Engines re-create lazily, so
the broad dispose is safe. 134 profile/delete tests green. Committed in `82b8a48f0`.

## Notes

Disposes all cached engines rather than resolving the single per-bucket URL: the
broad dispose is safe (lazy re-create) and guarantees the target handle is freed
cross-platform without the risk of a wrong URL-specific lookup.
