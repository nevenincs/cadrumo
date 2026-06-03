---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
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

The tests exercise real filesystem writes, parent-file write failures, missing-file loads, real pydantic validation, real AES-GCM encryption/decryption, real key mismatch failures, and persisted metadata tampering. They do not use fake/stub classes, mocks, monkeypatching, skip, or xfail shortcuts.

Validation:

- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/envelope/test_envelope.py src/aeat/adapters/persistence/storage/envelope/test_envelope_ciphertext.py` passed.
- `uv run --no-sync ruff check src/aeat/adapters/persistence/storage/envelope/_envelope.py src/aeat/adapters/persistence/storage/envelope/test_envelope.py src/aeat/adapters/persistence/storage/envelope/test_envelope_ciphertext.py` passed.
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md` passed with the known `PLAN022` ordering warning.
- `uv run --no-sync vaultspec-core vault check links` passed with existing stem-collision warnings.
- `uv run --no-sync -q python -m aeat.locales audit` failed on pre-existing `cli.config.init.*` missing keys in `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`. The missing keys are owned by CLI init translation work outside this envelope row and were not changed here.
- `uv run --no-sync vaultspec-core vault check body-links` and `uv run --no-sync vaultspec-core vault check dangling` failed on existing vault-wide unrelated records; this row's audit and exec documents contain wiki-links only in `related:` frontmatter.
- Touched-surface hygiene scan found no broad exception catches, unlogged suppressions, fake/stub/monkeypatch markers, skipped/xfail tests, direct output, local secure-object marker construction, direct settings construction, or direct environment access.

Review-agent note: spawning `vaultspec-code-reviewer` failed with `agent thread limit reached`, so the supervisor completed the same checklist locally.

Disposition: close `AFR-065` as `plaintext-exception`.
