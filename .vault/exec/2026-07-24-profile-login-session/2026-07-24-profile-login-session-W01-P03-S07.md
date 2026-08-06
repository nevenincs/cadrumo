---
tags:
  - '#exec'
  - '#profile-login-session'
date: '2026-07-24'
modified: '2026-07-24'
body_hash: 'sha256:bd6a4d6d36d577e8147415f8ae2e38dbcf47e100e8e1cd0d2b81c19868f85dfe'
step_id: 'S07'
related:
  - "[[2026-07-24-profile-login-session-plan]]"
---

# Implement the per-bucket failed-login throttle sidecar (plaintext counts and timestamps only, exponential 2^n seconds capped at 60, evaluated before any Argon2id derivation, counter reset on success and on logout) with the wait surfaced in the refusal context, verified by tests driving consecutive failures through the real file backend and asserting the enforced delays and the reset

## Scope

- `src/cadrumo/adapters/persistence/storage/master_key/_login_throttle.py`

## Description

- Run vaultspec-rag semantic search confirming no existing failed-login throttle or per-bucket counter-sidecar authority exists; pair with `rg` to rule out duplication.
- Add `_login_throttle.py` under the master-key substrate: a strict frozen `LoginThrottleState` (schema_version, consecutive_failures, last_failure_at) persisted as plaintext JSON beside the wrapped bucket DEK in the separated keystore directory, written through the existing hardened atomic secure-write helper.
- Implement the pure `evaluate_login_throttle` returning a typed `ThrottleEvaluation` (throttled, remaining_seconds, consecutive_failures) with exponential backoff `min(2 ** n, 60)` seconds measured from `last_failure_at`, so a caller checks the remaining wait before any Argon2id derivation and the KDF is never a timing oracle.
- Implement `record_login_failure` (increment + stamp) and `reset_login_throttle` (idempotent sidecar removal) for the success/logout clear path; no permanent lockout, best-effort revocable-cache semantics (missing/unreadable/version-mismatched file treated as cleared).
- Expose the public surface through the master-key package `__all__` facade.
- Add real-file tests under `master_key/tests/test_login_throttle.py` (controllable injected clock, no mocks/skips/xfail).

## Outcome

- New primitive `src/cadrumo/adapters/persistence/storage/master_key/_login_throttle.py` plus its `__init__.py` facade exports and `tests/test_login_throttle.py`.
- Gates green: `ruff check` clean on all three files; `pytest test_login_throttle.py` 20 passed; `pytest --collect-only` on the master_key package collects 222 tests with no errors.
- Scope respected: no wiring into login orchestration (deferred to W02.S08); `_bucket_session.py` (peer W01.P01 WIP) not touched.

## Notes

- Committing the storage sidecar was blocked by a stale `.git/index.lock` (0 bytes, frozen mtime, no live `git`/`pre-commit` process) held in the shared worktree; escalated to the coordinator for adjudication per the git-worktree-safety stop-and-report rule rather than removing the lock unilaterally.
