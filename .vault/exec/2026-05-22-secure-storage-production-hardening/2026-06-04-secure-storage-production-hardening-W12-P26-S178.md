---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S178'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s178-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S178`

Closed `AFR-076` for recovery-key primitives.

## Description

- Reviewed `src/aeat/adapters/persistence/storage/master_key/_recovery.py` against the `master-key` and `plain-file` scanner signals.
- Added a local storage-validation helper that binds BIP-39 entropy, mnemonic, checksum, master-key length, recovery-key length, malformed recovery JSON, and malformed recovery base64 failures to `errors.integrity.integrity_storage_validation`.
- Kept recovery-key generation, BIP-39 encoding, HKDF context, AES-GCM wrapping, and `master.recovery.key` JSON shape unchanged.
- Updated recovery tests to assert `StorageValidationError` and the translated message key for invalid entropy, word count, unknown words, checksum mismatch, master-key length, recovery-key length, malformed recovery JSON, and malformed recovery base64.
- Replaced the touched test's hardcoded encoding literal with `UTF_8_ENCODING`.

## Outcome

`AFR-076` is closed as a `bootstrap-custody` recovery primitive row.

Validation passed:

- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/master_key/test_recovery.py src/aeat/adapters/persistence/storage/master_key/test_recovery_facade.py`
- `uv run --no-sync ruff check src/aeat/adapters/persistence/storage/master_key/_recovery.py src/aeat/adapters/persistence/storage/master_key/test_recovery.py src/aeat/adapters/persistence/storage/master_key/test_recovery_facade.py`
- `uv run --no-sync -q python -m aeat.locales audit`
- Touched-surface hygiene scan found no broad exception suppressions, pragma/noqa/type-ignore suppressions, direct settings construction, naked environment access, fake/stub/monkeypatch markers, skipped/xfail tests, direct output, or naked encoding literals.

## Notes

No recovery mnemonic, raw recovery key, master key, nonce, ciphertext, or path value is added to structured error context by this step. Malformed recovery-file errors use generic messages so local paths are not rendered in user-facing envelopes.
