---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-W12-P26-S186]]'
---

# `secure-storage-production-hardening` `W12.P26.S186` Review

## S186-001 | PASS | ORM module is schema metadata only

`sql/_orm.py` declares SQLAlchemy mapped rows, constraints, relationships, encrypted column types, and metadata. It does not construct `SecureObjectRepository`, create engines or sessions, load settings, inspect environment variables, perform file IO, or catch exceptions.

## S186-002 | PASS | Secure-object columns remain encrypted at the ORM boundary

`SecureObjectRow.payload` remains mapped through `EncryptedBytes`, and natural object keys remain mapped through `HashedLookup`. The ORM schema therefore preserves the secure-object encryption and lookup boundary; runtime ownership is enforced by repository/runtime modules rather than this schema module.

## S186-003 | PASS | Validation exercised table metadata and secure-object behavior

The SQL constraint tests create a real SQLite schema from ORM metadata and issue raw SQL inserts that bypass pydantic model validation. The new checks reject `schema_version < 1` and malformed revision/hash metadata before those rows can become persisted secure-object state.

Validation:

- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/sql/test_constraints.py src/aeat/adapters/persistence/storage/sql/test_secure_objects.py::test_peek_metadata_reflects_on_disk_schema_version_drift` passed with 8 tests and existing SQLAlchemy datetime-adapter warnings.
- `uv run --no-sync ruff check src/aeat/adapters/persistence/storage/sql/_orm.py src/aeat/adapters/persistence/storage/sql/test_constraints.py` passed.
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.

Reviewer note: supervisor review found no critical or high issues in the S186 slice. The constraints align the database schema with existing repository/pydantic invariants, preserve future positive schema-version drift behavior, add no exception swallowing, and add no pragma/noqa suppression.

Disposition: close `AFR-084`.
