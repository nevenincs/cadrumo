---
tags:
  - '#exec'
  - '#storage-backend-security-review'
date: '2026-06-14'
modified: '2026-06-15'
step_id: 'S11'
related:
  - "[[2026-06-14-storage-backend-security-review-plan]]"
---




# Add a concurrent-writer regression proving two sessions on one bucket do not raise an immediate database-locked error

## Scope

- `src/aeat/adapters/persistence/storage/sql/tests/`

## Description

- Add `test_concurrent_writers_do_not_raise_database_locked`: four threads, each
  with its own engine over one bucket DB, run 25 inserts apiece behind a barrier;
  assert no writer raised and all 100 rows landed.
- Add `test_engine_applies_concurrency_pragmas` asserting busy_timeout=5000 and
  foreign_keys=1.

## Outcome

Real-behavior concurrency regression green. Per-thread engines guarantee each
SQLite connection is created and used in its owning thread. Committed in `47f95f61e`.

## Notes

The earlier discovery that WAL breaks ~21 at-rest raw-db readers is what drove the
busy_timeout-only scope; see S33.
