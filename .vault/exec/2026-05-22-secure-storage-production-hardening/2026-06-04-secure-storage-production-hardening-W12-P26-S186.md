---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S186'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s186-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S186`

Closed `AFR-084` for the SQL ORM schema module.

## Description

- Reviewed `src/aeat/adapters/persistence/storage/sql/_orm.py` against the `runtime-default` secure-object classification.
- Confirmed the module is schema metadata only and does not create runtime storage access.
- Verified `SecureObjectRow` keeps hashed lookup keys and encrypted payload columns.
- Added database-level `secure_objects` checks for positive schema versions and 64-character revision/hash metadata.
- Added real SQLite raw-insert constraint coverage in `src/aeat/adapters/persistence/storage/sql/test_constraints.py`.
- Validated the SQL constraint slice and secure-object schema-version drift behavior.
- Closed `AFR-084` and `W12.P26.S186`.

## Outcome

`AFR-084` is closed as a hardened ORM schema closure. Raw SQL writers can no longer persist impossible secure-object schema versions or malformed revision/hash metadata into newly created `secure_objects` tables.

Validation passed:

- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/sql/test_constraints.py src/aeat/adapters/persistence/storage/sql/test_secure_objects.py::test_peek_metadata_reflects_on_disk_schema_version_drift`
- `uv run --no-sync ruff check src/aeat/adapters/persistence/storage/sql/_orm.py src/aeat/adapters/persistence/storage/sql/test_constraints.py`
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit`

## Notes

The SQL constraint tests emitted existing SQLAlchemy sqlite datetime-adapter deprecation warnings for raw datetime parameters. No pragma/noqa suppressions were added.
