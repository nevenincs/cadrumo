---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
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
- Validated ORM metadata import and the SQL engine/secure-object behavior slice.
- Closed `AFR-084` and `W12.P26.S186`.

## Outcome

`AFR-084` is closed as an evidence-only ORM schema closure. No production code changes were required for this step.

Validation passed:

- `$env:PYTHONPATH='src'; uv run --no-sync python -c "from aeat.adapters.persistence.storage.sql._orm import Base, SecureObjectRow; assert 'secure_objects' in Base.metadata.tables; assert SecureObjectRow.__tablename__ == 'secure_objects'; print('orm secure object table ok')"`
- `uv run --no-sync ruff check src/aeat/adapters/persistence/storage/sql/_orm.py`
- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/sql/test_engine.py src/aeat/adapters/persistence/storage/sql/test_secure_objects.py`
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit`

## Notes

The SQL package tests emitted existing SQLAlchemy sqlite datetime-adapter deprecation warnings.
