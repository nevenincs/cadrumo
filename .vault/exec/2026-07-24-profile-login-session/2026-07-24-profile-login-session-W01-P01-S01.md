---
tags:
  - '#exec'
  - '#profile-login-session'
date: '2026-07-24'
modified: '2026-07-24'
step_id: 'S01'
related:
  - "[[2026-07-24-profile-login-session-plan]]"
---

# Extend BucketSession with opened_at and an immutable absolute_deadline, clamp touch() so the sliding idle deadline never passes the absolute deadline and make is_expired plus evaluate_idle enforce both limits, verified by new real-clock adapter tests that prove a continuously-touched session still seals at the absolute cap

## Scope

- `src/cadrumo/adapters/persistence/storage/master_key/_bucket_session.py`

## Description

- Add `opened_at` and an immutable `absolute_deadline` to `BucketSession`, fixed at `open()` as `opened_at + absolute_minutes` (fallback `DEFAULT_SESSION_ABSOLUTE_MINUTES = 240`).
- Add the `absolute_minutes` open parameter (optional, strict-positive validated) and expose `opened_at`/`absolute_deadline` properties; extend `__slots__`.
- Clamp the initial idle deadline to the absolute deadline at open, and clamp `touch()` so the sliding idle deadline never passes the absolute cap.
- Make `is_expired()` enforce both the idle window and the absolute cap; make `evaluate_idle()` report the earlier of the two deadlines as binding.
- Add a real-clock adapter test module proving a continuously-touched session still seals at the absolute cap, plus initial-clamp, cap-binding-remaining, and non-positive-absolute refusal cases.

## Outcome

Landed in commit `9dad0cbe8b` (message mislabelled `@` per the shared-worktree amend incident; content correct and complete). `ruff check` clean; `test_bucket_session_absolute_cap.py` and the full `master_key/tests` suite (231) pass under sequential `-n0`; existing `BucketSession.open` consumers (runtime, blob_store, diagnostics) stay green.

## Notes

The `absolute_minutes` parameter is optional/backward-compatible so every existing `BucketSession.open` caller (tests, dev packaging, recovery facade) keeps working on the 240-minute default. The zeroise/seal contract and `__slots__` discipline are preserved. Commit-message mislabel logged by the coordinator for campaign close review; history left as-is per direction (any fix would be a forbidden destructive-git op in this shared worktree).
