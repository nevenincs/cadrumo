---
tags:
  - '#exec'
  - '#storage-backend-security-review'
date: '2026-06-14'
modified: '2026-06-15'
step_id: 'S18'
related:
  - "[[2026-06-14-storage-backend-security-review-plan]]"
---




# Persist basename-only paths in the bucket exported and imported event payloads

## Scope

- `src/aeat/application/bucket_maintenance/_service.py`

## Description

- Replace `str(command.output_path)` / `str(command.source_path)` with `.name`
  (basename) in the BUCKET_EXPORTED / BUCKET_IMPORTED event payloads.

## Outcome

The durable bucket event log no longer bakes host-absolute paths (drive letter,
username, layout) that point nowhere on a restored host and leak the originating
layout. The manifest_digest remains the audit anchor. 6 tests green. Committed in
`9360769a6`.

## Notes

None.
