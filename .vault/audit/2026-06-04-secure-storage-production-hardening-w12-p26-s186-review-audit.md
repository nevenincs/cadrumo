---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
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

The import check confirmed the `secure_objects` table is present in `Base.metadata` and the SQL tests exercised engine table creation plus secure-object repository behavior against the ORM.

Validation:

- `$env:PYTHONPATH='src'; uv run --no-sync python -c "from aeat.adapters.persistence.storage.sql._orm import Base, SecureObjectRow; assert 'secure_objects' in Base.metadata.tables; assert SecureObjectRow.__tablename__ == 'secure_objects'; print('orm secure object table ok')"` passed.
- `uv run --no-sync ruff check src/aeat/adapters/persistence/storage/sql/_orm.py` passed.
- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/sql/test_engine.py src/aeat/adapters/persistence/storage/sql/test_secure_objects.py` passed with 45 tests and existing SQLAlchemy datetime-adapter warnings.
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.

Reviewer note: `vaultspec-code-reviewer` Locke found no issues. The reviewer confirmed `_orm.py` only defines declarative schema rows, keeps `SecureObjectRow.object_key` on `HashedLookup()`, keeps `SecureObjectRow.payload` on `EncryptedBytes()`, and has no repository, engine, session, settings, environment, file, raise, catch, print, repr, or logging surface requiring remediation.

Disposition: close `AFR-084`.
