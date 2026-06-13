---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S185'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s185-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S185`

Closed `AFR-083` for the SQL package facade.

## Description

- Reviewed `src/aeat/adapters/persistence/storage/sql/__init__.py` against the `runtime-default` secure-object classification.
- Confirmed the module is a re-export facade only and does not create repository, engine, session, settings, file, or environment behavior.
- Verified the expected facade exports and the current SQL package test slice.
- Closed `AFR-083` and `W12.P26.S185`.

## Outcome

`AFR-083` is closed as an evidence-only facade closure. No production code changes were required for this step.

Validation passed:

- `$env:PYTHONPATH='src'; uv run --no-sync python -c "from aeat.adapters.persistence.storage import sql; required = {'SecureObjectRepository','SecureObjectWrite','get_engine','session_scope'}; missing = sorted(required - set(sql.__all__)); assert not missing, missing; print('sql facade ok', sorted(required))"`
- `uv run --no-sync ruff check src/aeat/adapters/persistence/storage/sql/__init__.py`
- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/sql/test_engine.py src/aeat/adapters/persistence/storage/sql/test_session.py src/aeat/adapters/persistence/storage/sql/test_repository.py src/aeat/adapters/persistence/storage/sql/test_secure_objects.py`
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit`

## Notes

The SQL package tests emitted existing SQLAlchemy sqlite datetime-adapter deprecation warnings. A scoped hygiene scan of SQL tests found pre-existing `monkeypatch` use in `test_engine.py`; S185 did not touch that file.
