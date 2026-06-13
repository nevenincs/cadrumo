---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-W12-P26-S179]]'
---

# `secure-storage-production-hardening` `W12.P26.S179` Review

## S179-001 | PASS | Recovery facade reclassifies malformed envelope state

`_blob_from_envelope` now converts base64 and strict `EncryptedBlob` validation failures into `RecoveryVerificationError`, which binds to `errors.auth.auth_storage_bucket_recovery_verification`. `unwrap_recovery_envelope` also reclassifies lower-level storage validation during unwrap as recovery verification failure.

## S179-002 | PASS | Recovery diagnostics avoid secret and payload leakage

The facade does not render the operator mnemonic, recovery entropy, DEK, ciphertext, nonce, malformed base64 field, or file paths in the public error envelope. The malformed-envelope test asserts the rendered envelope stays typed without echoing the malformed field payload.

## S179-003 | PASS | Tests cover real facade behavior without shortcuts

The focused tests exercise BIP-39 reference vectors, real envelope mint/unwrap, wrong mnemonic, malformed mnemonic, malformed strict envelope shape, boolean verification, open-session composition, error-registry binding, and narrowed decoder exception behavior. They do not use fake/stub classes, mocks, monkeypatching, skip, or xfail shortcuts.

Validation:

- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/master_key/test_recovery_facade.py src/aeat/adapters/persistence/storage/master_key/test_recovery.py` passed with 33 tests.
- `uv run --no-sync ruff check src/aeat/adapters/persistence/storage/master_key/_recovery_facade.py src/aeat/adapters/persistence/storage/master_key/test_recovery_facade.py src/aeat/adapters/persistence/storage/master_key/test_recovery.py` passed.
- `uv run --no-sync -q python -m aeat.locales audit` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.
- Touched-surface hygiene scan found no broad exception suppressions, pragma/noqa/type-ignore suppressions, direct settings construction, naked environment access, fake/stub/monkeypatch markers, skipped/xfail tests, direct output, or naked encoding literals.

Review-agent note: spawning `vaultspec-code-reviewer` failed with `agent thread limit reached`, so the supervisor completed the same checklist locally.

Disposition: close `AFR-077` as `bootstrap-custody`.
