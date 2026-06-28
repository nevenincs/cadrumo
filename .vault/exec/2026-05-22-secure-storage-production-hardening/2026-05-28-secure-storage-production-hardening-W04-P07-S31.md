---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-28'
modified: '2026-05-28'
step_id: 'S31'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-22-secure-storage-production-hardening-architecture-adr]]'
  - '[[2026-05-22-secure-storage-production-hardening-architecture-research]]'
---

# `secure-storage-production-hardening` `W04.P07.S31`

Added bootstrap compatibility for existing secure-object tables that do not yet carry revision metadata.

- Modified: `src/aeat/adapters/persistence/storage/sql/secure_objects.py`
- Modified: `src/aeat/adapters/persistence/storage/sql/test_secure_objects.py`
- Reviewed: `.vault/audit/2026-05-28-secure-storage-production-hardening-W04-P07-S28-S31-review.md`

## Description

`SecureObjectRepository` now adds missing nullable revision metadata columns to existing `secure_objects` tables before ORM reads can select the new mapper fields. The bootstrap path re-inspects duplicate-column `OperationalError` cases and treats them as successful concurrent bootstrap only when the target column is present.

The quarantine archive path now creates or upgrades `secure_objects_quarantine` with the same revision metadata columns and copies those values when unreadable ciphertext is moved out of the live table.

## Tests

Validation used real SQLite tables and production encrypted column types. One regression starts from an old-shape `secure_objects` table and loads through the current repository. Another seals a row under an old key, annotates non-default revision metadata, quarantines it under a new key, and verifies the archive preserved metadata while deleting the source row.

- `uv run ruff check src/aeat/adapters/persistence/storage/sql/_orm.py src/aeat/adapters/persistence/storage/sql/secure_objects.py src/aeat/adapters/persistence/storage/sql/test_secure_objects.py`
- `uv run pytest src/aeat/adapters/persistence/storage/sql/test_secure_objects.py -q`
- `git diff --check -- src/aeat/adapters/persistence/storage/sql/_orm.py src/aeat/adapters/persistence/storage/sql/secure_objects.py src/aeat/adapters/persistence/storage/sql/test_secure_objects.py`
