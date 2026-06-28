---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-W12-P26-S177]]'
---

# `secure-storage-production-hardening` `W12.P26.S177` Review

## S177-001 | PASS | Bucket-DEK authentication failures are caught again

S174 changed `unwrap_dek` to surface AEAT `DecryptionError` instead of raw `InvalidTag`. `_load_or_mint_bucket_dek` now catches `DecryptionError`, so tampered or wrong-key bucket-DEK documents map back to the intended `MasterKeyUnavailableError` boundary.

## S177-002 | PASS | Local paths no longer leak through the new master-key paths

Bucket-DEK malformed-base64, malformed-field, read/parse, and authentication failures now use `errors.auth.auth_storage_master_key_unavailable`. Passphrase mismatch now uses `errors.auth.auth_storage_master_key_passphrase_mismatch` without embedding the local `master.key` path. Tests assert `str(tmp_path)` is absent from both exception text and JSON error envelopes.

## S177-003 | PASS | Exception handling is surfaced, not swallowed

Atomic-write cleanup no longer uses `contextlib.suppress`; cleanup failure is logged at debug and the original failure is re-raised. Keyring probe/get/set unexpected exceptions are converted to `KeyringUnavailableError` with debug breadcrumbs. The unsecured-profile decrypt branch now catches only `DecryptionError`, `TypeError`, and `ValueError`.

## S177-004 | PASS | Tests remain real-behavior

The new bucket-DEK tamper test provisions a real file-backed master key, activates a real bucket DEK enrollment, writes a real bucket manifest, corrupts the persisted wrapped-DEK tag, and verifies the production activation path. It does not use fake/stub classes, mocks, monkeypatching, skip, or xfail shortcuts.

Validation:

- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/master_key/test_master_key.py src/aeat/adapters/persistence/storage/master_key/test_master_key_errors.py src/aeat/adapters/persistence/storage/master_key/test_master_key_no_classvars.py src/aeat/adapters/persistence/storage/master_key/test_adverse_sessions.py src/aeat/adapters/persistence/storage/test_runtime.py` passed with 101 tests.
- `uv run --no-sync ruff check src/aeat/adapters/persistence/storage/master_key/_master_key.py src/aeat/adapters/persistence/storage/master_key/test_master_key.py src/aeat/adapters/persistence/storage/master_key/test_master_key_errors.py src/aeat/adapters/persistence/storage/master_key/test_master_key_no_classvars.py src/aeat/adapters/persistence/storage/master_key/test_adverse_sessions.py src/aeat/adapters/persistence/storage/test_runtime.py` passed.
- `uv run --no-sync -q python -m aeat.locales audit` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.
- Touched-surface hygiene scan found no pragma/noqa/type-ignore suppressions, direct output, naked encoding literals, monkeypatch/fake/stub markers, skipped/xfail tests, or direct test-shortcut markers in `_master_key.py` and `test_master_key.py`.

Review-agent note: spawning `vaultspec-code-reviewer` remains unavailable in this session due the agent thread limit, so the supervisor completed the same checklist locally.

Disposition: close `AFR-075` as `bootstrap-custody`.
