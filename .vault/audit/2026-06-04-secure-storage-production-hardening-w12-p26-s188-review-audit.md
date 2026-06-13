---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-W12-P26-S188]]'
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

- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/sql/test_secure_objects.py src/aeat/adapters/persistence/storage/sql/test_archive_bundle_roundtrip.py` passed with 45 tests and existing SQLAlchemy datetime-adapter warnings.
- `uv run --no-sync ruff check src/aeat/adapters/persistence/storage/sql/secure_objects.py src/aeat/adapters/persistence/storage/sql/test_secure_objects.py src/aeat/adapters/persistence/storage/sql/test_archive_bundle_roundtrip.py src/aeat/locales/test_parity.py src/aeat/locales/test_locale_translation_honesty.py` passed.
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.
- `uv run --no-sync pytest -q src/aeat/locales/test_parity.py src/aeat/locales/test_locale_translation_honesty.py` passed with 18 tests.
- The S188 hygiene scan found no env access, monkeypatches, fakes, stubs, mocks, suppressions, broad exception swallowing, or pragma shortcuts in the reviewed slice.

Reviewer note: Noether review found no issues in the S188 slice. Residual risk is limited to the focused S188 file set in a broadly dirty shared worktree. Remaining plaintext diagnostic reasons yielded by `iter_records_with_failures` are typed per-row diagnostic outcomes, not thrown exceptions; they should still be revisited in a later operator-output pass if those reasons are rendered directly by CLI commands.

Disposition: close `AFR-086`.
