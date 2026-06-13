---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S432'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-02-secure-storage-production-hardening-w05-p10-s43-review-audit]]'
---

# `secure-storage-production-hardening` `W06.P11.S432`

## Description

- Fixed the secure-object deterministic lookup regression by changing `SecureObjectRow.object_key` to `HashedLookup`.
- Added a legacy migration path for rows previously written with randomized `EncryptedString` keys.
- Quarantined duplicate or unmigratable legacy rows instead of silently discarding evidence.
- Covered legacy-key migration and duplicate-key quarantine with real SQLite and real encrypted-column decorators.

## Outcome

Closed.

The fix restored natural-key save/load, upsert convergence, profile Google folder configuration, and 32-byte mirror archive raw keys.

Validation:

- Pre-fix focused probes failed on secure-object load, upsert convergence, and archive raw-key length.
- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/sql/test_secure_objects.py src/aeat/adapters/persistence/storage/sql/test_archive_bundle_roundtrip.py` passed 42 tests with 3 sqlite datetime adapter warnings in legacy migration tests.
- `uv run --no-sync ruff check` passed for the touched secure-object SQL and encrypted-column files.
