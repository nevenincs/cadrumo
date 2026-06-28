---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S188'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s188-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S188`

Closed `AFR-086` for the SQL secure-object repository.

## Description

- Reviewed `src/aeat/adapters/persistence/storage/sql/secure_objects.py` against secure-object, manifest-bucket, master-key, SQL-route, plain-file, and remote-provider signals.
- Localized storage validation, repository upsert, unknown classification, classification mismatch, and schema mismatch failure paths.
- Removed natural-key and stored lookup-digest disclosure from load-time classification and schema-version failures.
- Replaced repository-local `"utf-8"` literals with the centralized `UTF_8_ENCODING` constant.
- Added focused real SQLite repository tests for translated raw-key validation, batch-size validation, schema-version drift redaction, and classification redaction.
- Validated remote-mirror raw iterator and archive-bundle behavior alongside the secure-object suite.
- Closed `AFR-086` and `W12.P26.S188`.

## Outcome

`AFR-086` is closed as a secure-object repository hardening slice. The repository now uses translated AEAT errors for the audited failure paths, keeps structured context, and avoids embedding object-key material in load-time exception messages.

Validation passed:

- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/sql/test_secure_objects.py src/aeat/adapters/persistence/storage/sql/test_archive_bundle_roundtrip.py`
- `uv run --no-sync ruff check src/aeat/adapters/persistence/storage/sql/secure_objects.py src/aeat/adapters/persistence/storage/sql/test_secure_objects.py src/aeat/adapters/persistence/storage/sql/test_archive_bundle_roundtrip.py src/aeat/locales/test_parity.py src/aeat/locales/test_locale_translation_honesty.py`
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit`
- `uv run --no-sync pytest -q src/aeat/locales/test_parity.py src/aeat/locales/test_locale_translation_honesty.py`

## Notes

The full secure-object suite passed with existing SQLAlchemy sqlite datetime-adapter warnings. Locale strings were updated via `python -m aeat.locales set`; the CLI was run with `PYTHONPATH=src` so the local package resolved without syncing the locked virtual environment.
