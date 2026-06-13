---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-W12-P26-S178]]'
---

# `secure-storage-production-hardening` `W12.P26.S178` Review

## S178-001 | PASS | Recovery validation uses localized AEAT errors

`encode_mnemonic`, `decode_mnemonic`, `wrap_master_key`, `unwrap_master_key`, `WrappedMasterKey.to_blob`, and `load_wrapped_master_key` now raise `StorageValidationError` with `errors.integrity.integrity_storage_validation` for invalid entropy length, mnemonic word count, unknown word position, checksum mismatch, master-key length, recovery-key length, malformed recovery JSON, and malformed recovery base64.

## S178-002 | PASS | Cryptographic and persistence shapes are unchanged

The row does not change BIP-39 index math, checksum derivation, the bundled wordlist, HKDF context, AEAD AAD, AES-GCM wrapping, or `WrappedMasterKey` JSON shape. Existing recovery roundtrip and persistence tests continue to exercise real encryption/decryption behavior.

## S178-003 | PASS | Tests avoid shortcut mechanisms

The focused tests assert real BIP-39 roundtrips, the canonical all-zero vector, wrong-length validation, unknown-word non-disclosure, checksum failure, case-insensitive decode, unique key generation, recovery-key-derived wrap/unwrap, wrong-key decrypt failure, atomic save/load roundtrip, malformed recovery JSON refusal, and malformed base64 refusal. They do not use fake/stub classes, mocks, monkeypatching, skip, or xfail shortcuts.

Validation:

- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/master_key/test_recovery.py src/aeat/adapters/persistence/storage/master_key/test_recovery_facade.py` passed with 32 tests.
- `uv run --no-sync ruff check src/aeat/adapters/persistence/storage/master_key/_recovery.py src/aeat/adapters/persistence/storage/master_key/test_recovery.py src/aeat/adapters/persistence/storage/master_key/test_recovery_facade.py` passed.
- `uv run --no-sync -q python -m aeat.locales audit` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.
- Touched-surface hygiene scan found no broad exception suppressions, pragma/noqa/type-ignore suppressions, direct settings construction, naked environment access, fake/stub/monkeypatch markers, skipped/xfail tests, direct output, or naked encoding literals.

Review-agent note: spawning `vaultspec-code-reviewer` remains unavailable in this session due the agent thread limit, so the supervisor completed the same checklist locally.

Disposition: close `AFR-076` as `bootstrap-custody`.
