---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-W12-P26-S167]]'
---

# `secure-storage-production-hardening` `W12.P26.S167` Review

## S167-001 | PASS | Plaintext envelope path is bounded and typed

`src/aeat/adapters/persistence/storage/envelope/_envelope.py` persists plaintext JSON only through `save_envelope`, which is the substrate-level `plaintext-exception` path for explicitly classified file-backed records and migrations. Loads enforce strict pydantic payload validation, expected sensitivity classification, maximum supported schema version, and monotonic migrator chains.

Read, parse, and write failures are wrapped in localized `StorageValidationError` without including filesystem paths. Atomic writes use temporary files in the target directory, `os.replace`, file fsync, and parent-directory fsync; failed cleanup attempts are logged at debug level.

## S167-002 | PASS | Encrypted envelope path binds master key usage to consumer context

Encrypted envelopes derive a per-consumer key from the supplied master-key provider via HKDF and bind both classification and HKDF context into AEAD associated data. The on-disk cipher envelope contains ciphertext metadata and no typed payload field.

Load rejects wrong outer classification before master-key access, rejects AAD drift, rejects wrong master keys, revalidates the inner plaintext envelope after decryption, and applies the same schema-version and migrator gates as plaintext loads.

## S167-003 | PASS | Diagnostics and tests enforce redacted typed failures

Filesystem paths were removed from envelope classification, version, AAD, and corrupted-inner-envelope messages. Write failure logs record only the exception type. The re-encrypt path still treats non-cipher JSON as a plaintext migration candidate, but it records the parse failure at debug level before continuing.

The implementation and direct tests now route text encoding and decoding through `UTF_8_ENCODING`. The generic envelope factory no longer carries `type: ignore`; it uses an explicit `cast` with a local rationale that names the pydantic generic runtime contract.

The tests exercise real filesystem writes, parent-file write failures, missing-file loads, real pydantic validation, real AES-GCM encryption/decryption, real key mismatch failures, and persisted metadata tampering. They do not use fake/stub classes, mocks, monkeypatching, skip, or xfail shortcuts.

Validation:

- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/envelope/test_envelope.py src/aeat/adapters/persistence/storage/envelope/test_envelope_ciphertext.py` passed.
- `uv run --no-sync ruff check src/aeat/adapters/persistence/storage/envelope/_envelope.py src/aeat/adapters/persistence/storage/envelope/test_envelope.py src/aeat/adapters/persistence/storage/envelope/test_envelope_ciphertext.py` passed.
- `uv run --no-sync -q python -m aeat.locales audit` passed.
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md` passed with the known `PLAN022` ordering warning.
- Touched-surface hygiene scan found no broad exception catches, suppressions, fake/stub/monkeypatch markers, skipped/xfail tests, direct output, direct encoding literals, pragma/noqa/type-ignore directives, local secure-object marker construction, direct settings construction, or direct environment access.

Review-agent note: a reviewer subagent was unavailable in this session due the current usage limit, so the supervisor completed the same checklist locally.

Disposition: close `AFR-065` as `plaintext-exception`.
