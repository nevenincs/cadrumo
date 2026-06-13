---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S76'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
  - '[[2026-06-03-live-iva-compensation-wallet-code-review-audit]]'
---

# W09.P21.S76 database-backed test password guard

Scope: Verify database-backed tests use the central dev/test database password surface rather than ad hoc literals.

## Description

- Reviewed the existing `aeat.tests.secure_sql` helpers.
- Verified `test_database_operating_passphrases_use_core_test_setting` scans database-operating tests for literal passphrase callbacks and literal `aeat_secret_passphrase` / `AEAT_SECRET_PASSPHRASE` overrides.
- Ran a supplemental text scan for passphrase literals and classified remaining matches as non-database master-key, auth, LLM, or sanitizer unit-test fixtures.

## Verification

- `PYTHONPATH=src .venv\Scripts\python.exe -m pytest -q src/aeat/adapters/persistence/storage/test_ephemeral_key_hygiene.py src/aeat/tests/test_secure_sql.py` passed with 7 tests.
- `PYTHONPATH=src .venv\Scripts\python.exe -m ruff check src/aeat/adapters/persistence/storage/test_ephemeral_key_hygiene.py src/aeat/tests/test_secure_sql.py src/aeat/tests/secure_sql.py` passed.

## Notes

This closes the database-backed test password step only. It does not claim that all passphrase literals in pure master-key/auth/sanitizer unit tests are removed. No live AEAT request was made. No AEAT filing, payment, confirmation, represented-taxpayer selection, or write path was executed.
