---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-10-03'
body_hash: 'sha256:48d2337e3624814f8013ff13e62e7b1d6a8fb32f5e61d7a96df618f6e9314ac9'
related: []
---

# `secure-storage-production-hardening` `W12.P26.S188` Review

## S188-001 | PASS | Secure-object failure paths use AEAT translated errors

The audited `StorageValidationError`, `RepositoryError`, `ClassificationError`, and `EnvelopeVersionError` paths now carry `translated_message` keys and structured context. New locale leaves were added and corrected through `python -m aeat.locales set`, and `python -m aeat.locales audit` passes for all locale files.

## S188-002 | PASS | Load-time failures do not expose object-key material

The repository no longer embeds natural keys or stored lookup-digest hex in load-time classification and schema-version exceptions. Focused tests mutate real persisted rows, read the stored lookup digest from SQLite, and assert that neither the natural key nor digest appears in the rendered exception text.

## S188-003 | PASS | Constants are centralized for repository byte encoding

`secure_objects.py` now uses `UTF_8_ENCODING` from the core external constants module instead of local `"utf-8"` literals. A fixed-string scan confirmed no literal `utf-8` remains in the repository file.

## S188-004 | PASS | Remote-mirror and quarantine behavior remains ciphertext-safe

The raw iterator still reads SQL rows without decrypting and yields ciphertext plus metadata for remote mirror consumers. Quarantine still copies encrypted payload, revision metadata, integrity hashes, provenance, and source event metadata before deleting source rows.

## S188-005 | PASS | Tests exercise real behavior without fakes or monkeypatching

The added tests use `EphemeralMasterKeyProvider`, real SQLite engines, ORM metadata, and repository calls. They do not introduce fakes, stubs, monkeypatches, skips, xfails, or tautological mirror logic.

Validation:

- the historical check passed with 45 tests and existing SQLAlchemy datetime-adapter warnings.
- the historical check passed.
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.
- the historical check passed with 18 tests.
- The S188 hygiene scan found no env access, monkeypatches, fakes, stubs, mocks, suppressions, broad exception swallowing, or pragma shortcuts in the reviewed slice.

Reviewer note: Noether review found no issues in the S188 slice. Residual risk is limited to the focused S188 file set in a broadly dirty shared worktree. Remaining plaintext diagnostic reasons yielded by `iter_records_with_failures` are typed per-row diagnostic outcomes, not thrown exceptions; they should still be revisited in a later operator-output pass if those reasons are rendered directly by CLI commands.

Disposition: close `AFR-086`.
