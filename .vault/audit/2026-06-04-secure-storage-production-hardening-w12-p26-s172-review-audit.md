---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-W12-P26-S172]]'
---

# `secure-storage-production-hardening` `W12.P26.S172` Review

## S172-001 | PASS | Active-session errors stay in the AEAT hierarchy

`NoActiveBucketSessionError` continues to derive from `SecretStoreError`, so callers can catch it through the storage and AEAT base hierarchy. The error now preserves the remediation detail as its exception message while retaining the translated message key `errors.refused.refused_storage_master_key_no_active_session`.

## S172-002 | PASS | Shutdown cleanup no longer swallows without diagnostics

The atexit cleanup hook remains best-effort and must not raise during interpreter shutdown. Its broad `Exception` catch now logs a debug breadcrumb with the exception type before returning, satisfying the no-silent-swallow rule while preserving shutdown safety.

## S172-003 | PASS | No settings, environment, or key acquisition introduced

The active-session module uses a `ContextVar` to bind an already-open `BucketSession`. It does not read settings, inspect environment variables, open keyring/file backends, derive keys, or acquire master-key material. Expired sessions are closed before raising `BucketLockedError`, preserving the fail-closed path.

## S172-004 | PASS | Tests cover real behavior

The focused tests exercise the no-active-session error, locked-session refusal, expired-session sealing, wrong-passphrase activation failure, and torn-manifest activation failure through real `BucketSession`, file-backed provider, manifest, settings override, and storage code paths. They do not introduce fake/stub classes, mocks, monkeypatching, skip, or xfail shortcuts.

Validation:

- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/master_key/test_adverse_sessions.py` passed with 5 tests.
- `uv run --no-sync ruff check src/aeat/adapters/persistence/storage/master_key/_active_session.py src/aeat/adapters/persistence/storage/master_key/test_adverse_sessions.py` passed.
- Touched-surface hygiene scan found no direct environment access, settings construction, keyring calls, file I/O calls, fake/stub/monkeypatch markers, skipped/xfail tests, or direct output. The only broad exception match is the logged atexit cleanup guard.

Review-agent note: spawning `vaultspec-code-reviewer` failed with `agent thread limit reached`, so the supervisor completed the same checklist locally.

Disposition: close `AFR-070` as `bootstrap-custody`.
