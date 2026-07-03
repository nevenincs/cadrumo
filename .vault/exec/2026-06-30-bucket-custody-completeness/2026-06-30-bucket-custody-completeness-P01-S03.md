---
tags:
  - '#exec'
  - '#bucket-custody-completeness'
date: '2026-06-30'
modified: '2026-06-30'
step_id: 'S03'
related:
  - "[[2026-06-30-bucket-custody-completeness-plan]]"
---

# Add a registry projection helper returning the carry-set namespaces per custody profile

## Scope

- `src/aeat/adapters/persistence/storage/_namespace_registry.py`

## Description

- Add `StorageHierarchyRegistry.namespaces_for_custody_profile`.
- Define profile membership so full custody carries structured and
  full-custody-only namespaces, while structured custody carries only
  structured namespaces.
- Add a registry projection test proving cross-period inputs are in both
  profiles, evidence/live/audit-byte stores are full-only, and the participation
  index is excluded.
- Re-export the custody profile enum through the storage package API.

## Outcome

P01.S03 is complete. Later serialization and coverage-gate phases can now ask
the registry for a custody-profile carry set rather than maintaining a separate
transport list.

Verification:

- `uvx vaultspec-rag search "bucket custody completeness namespace registry disposition full structured evidence observations participation index" --type code --port 8766`
- `uv run --no-sync pytest src/aeat/adapters/persistence/storage/tests/test_namespace_registry.py src/aeat/application/tests/test_namespace_registry_adoption.py src/aeat/adapters/persistence/storage/sql/tests/test_secure_objects_part2.py`
- `uv run --no-sync ruff check src/aeat/adapters/persistence/storage/_namespace_registry.py src/aeat/adapters/persistence/storage/__init__.py src/aeat/adapters/persistence/storage/tests/test_namespace_registry.py src/aeat/adapters/persistence/storage/sql/tests/_secure_objects_support.py src/aeat/adapters/persistence/storage/sql/tests/test_secure_objects_part2.py`

The mandatory code-review pass found one HIGH classification issue:
`ledger_business_operation_invoices` was incorrectly full-only. That finding is
resolved in this step by classifying the namespace as `STRUCTURED_CUSTODY` and
asserting that it appears in both full and structured custody profiles. The
remaining risk is deferred to later phases: the projection must still be
consumed by the schema, serializer, importer, and non-tautological full
roundtrip tests.

## Notes

The final code-review finding was resolved before commit.
