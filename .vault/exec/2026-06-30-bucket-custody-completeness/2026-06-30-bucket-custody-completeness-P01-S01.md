---
tags:
  - '#exec'
  - '#bucket-custody-completeness'
date: '2026-06-30'
modified: '2026-07-17'
step_id: 'S01'
related:
  - "[[2026-06-30-bucket-custody-completeness-plan]]"
---

# Add StorageCustodyDisposition enum and a required custody_disposition field to SecureObjectNamespaceDefinition

## Scope

- `src/aeat/adapters/persistence/storage/_namespace_registry.py`

## Description

- Add `StorageCustodyDisposition` to classify each secure-object namespace as
  structured custody, full-custody-only, derived rebuildable, or process-local.
- Add `StorageCustodyProfile` for the two transport profiles used by later
  bundle work.
- Make `custody_disposition` a required field on
  `SecureObjectNamespaceDefinition`.
- Re-export the new enum types through the storage package API.

## Outcome

P01.S01 is complete. The registry model now requires every namespace definition
to carry explicit custody intent before the registry can instantiate.

Verification:

- `uvx vaultspec-rag search "StorageCustodyDisposition SecureObjectNamespaceDefinition custody_disposition carry set namespace registry" --type code --port 8766`
- `uv run --no-sync pytest src/aeat/adapters/persistence/storage/tests/test_namespace_registry.py src/aeat/application/tests/test_namespace_registry_adoption.py src/aeat/adapters/persistence/storage/sql/tests/test_secure_objects_part2.py`
- `uv run --no-sync ruff check src/aeat/adapters/persistence/storage/_namespace_registry.py src/aeat/adapters/persistence/storage/__init__.py src/aeat/adapters/persistence/storage/tests/test_namespace_registry.py src/aeat/adapters/persistence/storage/sql/tests/_secure_objects_support.py src/aeat/adapters/persistence/storage/sql/tests/test_secure_objects_part2.py`
- `git diff --check -- src/aeat/adapters/persistence/storage/_namespace_registry.py src/aeat/adapters/persistence/storage/__init__.py src/aeat/adapters/persistence/storage/tests/test_namespace_registry.py`

The focused pytest run passed with 56 tests. Ruff passed. Diff check reported
only line-ending normalization warnings on touched Windows files.

## Notes

This step intentionally establishes authority only. It does not yet serialize or
import carried objects; those behaviors are covered by later phases.
The required field also required a SQL secure-object split test fixture to pass
an explicit structured-custody disposition.
