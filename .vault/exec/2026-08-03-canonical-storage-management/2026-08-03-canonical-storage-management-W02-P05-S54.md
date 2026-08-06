---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:2078de370d68335cfc7edb9bc1f839c1d9877b51514e470b96fc09c9aafb9c13'
step_id: 'S54'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Re-point the default log file path onto the accessor, gated by the existing logging tests plus the rendered-help assertion naming the resolved log directory

## Scope

- `src/cadrumo/core/logging.py`

## Description

- Re-point the default log file path onto the accessor.

## Outcome

Landed in commit `20b8c2559f` ("resolve the diagnostic log path through the taxonomy accessor"), which landed during this reconciliation session, after this backfill pass had already begun. `default_log_file_path()` (`core/logging.py:401`) now reads `storage_path(StorageCategory.LOGS).expanduser() / _DEFAULT_LOG_FILE_NAME` instead of a direct settings read.

## Notes

This Step flipped to `checked: true` in the shared plan mid-session with no exec record and without me checking it — the same unaccountable-checkbox pattern flagged for S42. Verified against current code before writing this record rather than trusting the checkbox; confirmed genuinely done by a peer commit, not a false positive.
