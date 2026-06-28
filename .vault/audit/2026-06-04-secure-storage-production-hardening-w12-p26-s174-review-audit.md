---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-W12-P26-S174]]'
---

# `secure-storage-production-hardening` `W12.P26.S174` Review

## S174-001 | PASS | DEK unwrap failures stay inside AEAT exceptions

`unwrap_dek` no longer lets `cryptography.exceptions.InvalidTag` escape the storage boundary. Wrong KEK, wrong bucket AAD, tampered tag, and tampered ciphertext now raise `DecryptionError` with the original cryptography exception chained as `__cause__`. The user-facing message does not include bucket ids, paths, key material, ciphertext, nonce, or tag bytes.

## S174-002 | PASS | DEK wrap validation remains typed

`wrap_dek` continues to reject wrong-size KEK, wrong-size DEK, and empty bucket id through `EncryptionError`. AES-GCM wrap failures are converted to `EncryptionError`. Associated data now encodes through the shared UTF-8 encoding constant rather than a naked default.

## S174-003 | PASS | Tests exercise real cryptography behavior

The focused tests retain the upstream AES-GCM known-answer vector, random nonce roundtrip, fresh nonce property, wrong-key failure, wrong-bucket AAD failure, tag tamper failure, ciphertext tamper failure, validation failures, and strict pydantic field-length enforcement. They do not use fake/stub classes, mocks, monkeypatching, skip, or xfail shortcuts.

Validation:

- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/master_key/test_dek_wrap.py src/aeat/adapters/persistence/storage/master_key/test_dek_wrap_errors.py` passed with 16 tests.
- `uv run --no-sync ruff check src/aeat/adapters/persistence/storage/master_key/_dek_wrap.py src/aeat/adapters/persistence/storage/master_key/test_dek_wrap.py src/aeat/adapters/persistence/storage/master_key/test_dek_wrap_errors.py` passed.
- `uv run --no-sync -q python -m aeat.locales audit` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.
- Touched-surface hygiene scan found no broad exception suppressions, direct settings construction, naked environment access, fake/stub/monkeypatch markers, skipped/xfail tests, or direct output.

Review-agent note: spawning `vaultspec-code-reviewer` failed with `agent thread limit reached`, so the supervisor completed the same checklist locally.

Disposition: close `AFR-072` as `bootstrap-custody`.
