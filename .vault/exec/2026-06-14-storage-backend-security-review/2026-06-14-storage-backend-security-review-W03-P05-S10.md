---
tags:
  - '#exec'
  - '#storage-backend-security-review'
date: '2026-06-14'
modified: '2026-06-15'
step_id: 'S10'
related:
  - "[[2026-06-14-storage-backend-security-review-plan]]"
---




# Set SQLite busy_timeout in the bucket engine connect listener so a concurrent invocation waits rather than failing immediately with database-locked

## Scope

- `src/aeat/adapters/persistence/storage/sql/engine.py`

## Description

- Add `PRAGMA busy_timeout=5000` (new `_SQLITE_BUSY_TIMEOUT_MS` constant) to the
  bucket engine connect listener; rename `_enable_sqlite_foreign_keys` to
  `_attach_sqlite_pragmas` and refresh the module/function docstrings.

## Outcome

A concurrent `aeat` invocation that meets a held lock now waits up to five seconds
instead of failing immediately with SQLITE_BUSY. `synchronous` stays at the
rollback-journal-safe FULL default. Committed in `47f95f61e`.

## Notes

WAL (the larger concurrency win) was descoped to W03.P05.S33: enabling it adds a
`-wal` sidecar that ~21 at-rest raw-db test readers across the codebase must learn
to scan (several are peer-WIP), so it is not cleanly landable in this commit.
