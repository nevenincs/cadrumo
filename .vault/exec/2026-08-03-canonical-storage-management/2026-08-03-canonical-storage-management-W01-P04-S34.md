---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:541c6a2cd2be44deed055b54adfb688c89897060177e4dbedea454396b43cbf4'
step_id: 'S34'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Add directory_byte_total returning bytes and file count with optional stat-error tolerance, gated by a test that removes a file mid-walk and asserts the tolerant mode returns a partial total while the strict mode raises

## Scope

- `src/cadrumo/core/paths.py`

## Description

- Add `directory_byte_total` in `core/paths.py` returning bytes and file count, with optional per-file stat-error tolerance.

## Outcome

Landed in commit `095bdc4ca2`.

## Notes

The prior reconciliation pass (`bb18425074`) checked this Step, and separately checked S37 (`select_filesystem_retention_survivors`), before either primitive existed in `core/paths.py`. Between that mark and `095bdc4ca2`, HEAD held an already-committed test module and already-committed production code (`entrypoints/mcp/_telemetry.py`) both referencing `select_filesystem_retention_survivors`, which did not exist — a broken-HEAD window, closed by `095bdc4ca2`. Recorded here for honesty; the Step is now genuinely satisfied.
