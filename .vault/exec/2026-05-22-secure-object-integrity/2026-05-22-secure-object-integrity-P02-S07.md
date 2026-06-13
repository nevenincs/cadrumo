---
tags:
  - '#exec'
  - '#secure-object-integrity'
date: '2026-05-22'
modified: '2026-05-22'
step_id: 'S07'
related:
  - '[[2026-05-22-secure-object-integrity-attribution-plan]]'
---




# `secure-object-integrity` `P02.S07`

Added shared helper code for accepted secure SQL test isolation.

- Created: `src/aeat/tests/secure_sql.py`
- Created: `src/aeat/tests/test_secure_sql.py`

## Description

Added `isolated_ephemeral_secure_sql`, a test helper that sets a temporary SQLite `AEAT_DATABASE_URL`, disposes cached SQL engines before and after the isolated block, and opens a real `EphemeralMasterKeyProvider`. This encodes the accepted isolation pattern in reusable test helper code rather than prose-only documentation.

Added a real-behavior helper test proving the default SQL engine routes to the temporary database while the helper is active and that the ephemeral session is closed afterward.

## Tests

Focused validation passed:

- `uv run ruff check src/aeat/tests/secure_sql.py src/aeat/tests/test_secure_sql.py src/aeat/adapters/persistence/storage/test_ephemeral_key_hygiene.py`
- `uv run pytest src/aeat/tests/test_secure_sql.py src/aeat/adapters/persistence/storage/test_ephemeral_key_hygiene.py`

The focused test run passed 3 tests.
