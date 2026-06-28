---
tags:
  - '#exec'
  - '#storage-backend-security-review'
date: '2026-06-14'
modified: '2026-06-15'
step_id: 'S12'
related:
  - "[[2026-06-14-storage-backend-security-review-plan]]"
---




# fsync the staged tmp file and the parent directory before and after os.replace on the manifest write

## Scope

- `src/aeat/adapters/persistence/storage/bucket/_manifest_io.py`

## Description

- Rewrite `write_manifest` to open the `.tmp` sibling explicitly, `flush` +
  `os.fsync` the fd before `os.replace`, then `fsync_parent_dir(target)` after.

## Outcome

The manifest atomic write is now power-loss durable (matching the rotation
atomic-write path): a hard crash can no longer leave a zero-length manifest that
reads back as ProfileNotFound for a live bucket. 109 bucket tests green.
Committed in `382b5c08e`.

## Notes

None.
