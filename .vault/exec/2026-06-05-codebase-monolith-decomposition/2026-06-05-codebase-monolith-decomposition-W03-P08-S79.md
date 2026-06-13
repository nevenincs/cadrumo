---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S79'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W03.P08.S79 SQL Secure Objects Decomposition

Scope: decompose SQL secure objects persistence by row, crypto, and repository concerns behind the storage facade.

## Description

- Extract secure-object pydantic row and metadata records into `src/aeat/adapters/persistence/storage/sql/_secure_object_records.py`.
- Extract deterministic SHA-256 and revision-id derivation helpers into `src/aeat/adapters/persistence/storage/sql/_secure_object_crypto.py`.
- Extract secure-object schema bootstrap, revision-metadata DDL, ancestry parsing, and quarantine row-copy helpers into `src/aeat/adapters/persistence/storage/sql/_secure_object_schema.py`.
- Extract legacy randomized object-key migration into `src/aeat/adapters/persistence/storage/sql/_secure_object_migration.py`.
- Extract decryptability diagnostics and unreadable-row quarantine behavior into `src/aeat/adapters/persistence/storage/sql/_secure_object_integrity.py`.
- Keep `src/aeat/adapters/persistence/storage/sql/secure_objects.py` as the repository orchestration and compatibility facade for existing imports.
- Preserve the top-level SQL storage facade exports in `src/aeat/adapters/persistence/storage/sql/__init__.py`.
- Repair the explicit S80 redaction/error-typing test path so it loads `src/aeat/application/user_profile/_censo_errors.py` from the real application package path.

## Outcome

SQL secure-object row models, revision crypto helpers, schema bootstrap, legacy key migration, and decryptability/quarantine diagnostics are separated from repository orchestration without changing repository behavior or consumer-facing storage imports. `secure_objects.py` now stays below the hard 1250-line module budget at 1169 lines.

## Notes

No application, entrypoint, or domain consumer imports the new private records, crypto, schema, migration, or integrity modules directly.
