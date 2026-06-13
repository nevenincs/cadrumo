---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-27'
modified: '2026-05-27'
step_id: 'S412'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# `secure-storage-production-hardening` `W15.P33.S412`

Inventoried bucket paths, object-key grammar, namespace strings, schema versions, and repair classifications.

- Added: `.vault/audit/2026-05-27-secure-storage-hierarchy-namespace-inventory.md`

## Description

The inventory records the persistent bucket hierarchy, secure-object table grammar, blob/secret schema-version constants, repair decision custody, application namespace entries, and registered domain/adapter namespace follow-ups.

The audit identifies the remaining duplicated-value pressure: schema version `1`, singleton keys such as `catalogue` and `state`, bucket path segments, and local namespace strings spread across application, domain, and adapter modules.

## Tests

Passed:

- `uv run pytest -q src/aeat/adapters/persistence/storage/test_namespace_registry.py src/aeat/adapters/persistence/storage/bucket/test_layout.py src/aeat/adapters/persistence/storage/bucket/test_manifest_io.py src/aeat/adapters/persistence/storage/bucket/test_keystore_paths.py src/aeat/application/user_profile/test_repository.py src/aeat/application/workflow/test_persistence.py src/aeat/application/live/test_census_snapshot.py src/aeat/application/live/test_borrador_100.py src/aeat/application/test_repair_integrity.py src/aeat/application/calculations/test_observations_repository_roundtrip.py src/aeat/application/calculations/test_iva_compensation_history.py src/aeat/application/filing/test_history_repository.py src/aeat/application/filing/test_history_repository_roundtrip.py src/aeat/application/auth/test_apoderado.py src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py`
