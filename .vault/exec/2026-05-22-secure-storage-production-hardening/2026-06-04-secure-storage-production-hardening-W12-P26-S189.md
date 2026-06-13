---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S189'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s189-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S189`

Closed `AFR-087` for the SQL session unit-of-work helper.

## Description

- Reviewed `src/aeat/adapters/persistence/storage/sql/session.py` against the `runtime-default` SQL-route classification.
- Confirmed `session_scope` commits on success, rolls back on exception, logs rollback at debug with exception information, re-raises, and always closes the session.
- Repaired `src/aeat/adapters/persistence/storage/sql/test_session.py` to use `StorageValidationError` rather than a local sentinel exception class.
- Added explicit rollback debug-log coverage.
- Closed `AFR-087` and `W12.P26.S189`.

## Outcome

`AFR-087` is closed as a session-scope convention and diagnostics hardening slice. No production code change was required; the existing helper already avoided swallowing exceptions and logged rollback diagnostics.

Validation passed:

- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/sql/test_session.py`
- `uv run --no-sync ruff check src/aeat/adapters/persistence/storage/sql/session.py src/aeat/adapters/persistence/storage/sql/test_session.py`
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit`
- `if (rg "_Fake|_Stub|monkeypatch|skip|xfail|class .*Error|pass$" src/aeat/adapters/persistence/storage/sql/test_session.py) { exit 1 }`

## Notes

No pragma/noqa suppressions were added.
