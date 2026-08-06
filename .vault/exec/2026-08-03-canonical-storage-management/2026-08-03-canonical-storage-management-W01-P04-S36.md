---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:089e97a22a70e81b562ba4428ffa64ccdb74a2e9bf59a0ad21c49511a71287ed'
step_id: 'S36'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Rewrite the bucket-maintenance directory byte total as a caller of the shared helper in tolerant mode, gated by the existing disk-usage report tests plus a new race-tolerance assertion

## Scope

- `src/cadrumo/application/bucket_maintenance/_service.py`

## Description

- Rewrite the bucket-maintenance directory byte total as a caller of `directory_byte_total` in tolerant mode.
- Gains per-file `OSError` tolerance as a side effect, closing a latent crash when a blob write races the read (reproduced with a real concurrent thread, not a mock).

## Outcome

Landed in commit `095bdc4ca2`.

## Notes

Same premature-checkbox / broken-HEAD history as S34; see that record.
