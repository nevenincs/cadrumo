---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-W12-P26-S173]]'
---

# `secure-storage-production-hardening` `W12.P26.S173` Review

## S173-001 | PASS | Bucket session remains instance-scoped custody

`src/aeat/adapters/persistence/storage/master_key/_bucket_session.py` keeps KEK and DEK material in per-instance `bytearray` buffers. It does not reintroduce provider `ClassVar` state or module-global key caches. `close()` zeroises both buffers before sealing the session and is idempotent.

The `kek` and `dek` properties still materialise immutable `bytes` copies; this is documented as a Python-language limitation rather than claimed as guaranteed deep zeroisation.

## S173-002 | PASS | Engine eviction now uses the centralized settings route helper

The bucket engine route is now derived through `settings_for_active_profile_bucket(self._bucket_id, load_settings())`, so route construction stays in the settings core instead of being rebuilt in the master-key module. Explicit primary database URLs fail closed at the helper boundary and trigger a fallback `dispose_engine()` of every cached engine.

Targeted-route fallback, targeted dispose failure, and fallback dispose failure all log redacted debug diagnostics by exception type only. No filesystem path, bucket root, SQL URL, or key material is included in those diagnostics.

## S173-003 | PASS | Broad cleanup swallowing was removed

The previous broad engine-eviction catch is gone. The implementation now catches the expected settings-route validation failures and SQLAlchemy cleanup failures explicitly. Cleanup remains best-effort after key buffers are zeroised, so an engine-cache problem cannot preserve cleartext key material.

## S173-004 | PASS | Tests are real behavior and non-tautological

The new regression test opens a real `BucketSession`, enters a real `override_settings` block with an explicit `aeat_database_url`, calls `close()`, and asserts the session sealed and the debug fallback message is path-redacted. Existing focused coverage exercises wrong-passphrase activation, torn manifest activation, locked sessions, expired sessions, runtime guards, and real master-key providers.

Validation:

- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/master_key/test_adverse_sessions.py src/aeat/adapters/persistence/storage/master_key/test_master_key.py src/aeat/adapters/persistence/storage/test_runtime.py` passed with 94 tests.
- `uv run --no-sync ruff check src/aeat/adapters/persistence/storage/master_key/_bucket_session.py src/aeat/adapters/persistence/storage/master_key/test_adverse_sessions.py src/aeat/adapters/persistence/storage/master_key/test_master_key.py src/aeat/adapters/persistence/storage/test_runtime.py` passed.
- `uv run --no-sync -q python -m aeat.locales audit` passed.
- Touched-surface hygiene scan found no broad exception catches, suppressions, fake/stub/monkeypatch markers, skipped/xfail tests, direct output, direct encoding literals, direct settings construction, direct environment access, or local secure-object marker construction.

Review-agent note: a reviewer subagent was unavailable in this session due the current usage limit, so the supervisor completed the same checklist locally.

Disposition: close `AFR-071` as `bootstrap-custody`.
