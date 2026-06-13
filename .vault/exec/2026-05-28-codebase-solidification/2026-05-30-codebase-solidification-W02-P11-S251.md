---
step_id: S251
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-30
modified: '2026-05-30'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# codebase-solidification W02.P11.S251

## Outcome

Migrated 5 `ValueError` raises in `_bucket_session.py` and 1 in `_idle_timeout.py` to `StorageValidationError`:
- `BucketSession.open` lines 97-103: empty bucket_id, non-positive idle_minutes, wrong-size kek, wrong-size dek.
- `evaluate_idle` line 69: non-positive configured_minutes.

`StorageValidationError` inherits from `(PersistenceError, ValueError)` so pre-existing `pytest.raises(ValueError)` assertions in `test_bucket_session.py` and `test_idle_timeout.py` continue to pass without modification.

## Test result

12 bucket_session + 10 idle_timeout tests all pass.

## Files touched

- `src/aeat/adapters/persistence/storage/master_key/_bucket_session.py` — 4 ValueError → StorageValidationError
- `src/aeat/adapters/persistence/storage/master_key/_idle_timeout.py` — 1 ValueError → StorageValidationError
