---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S2131'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
  - '[[2026-05-12-cli-workflow-redesign-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-bucket-adr]]'
  - '[[2026-06-03-cli-workflow-redesign-adr]]'
---

# W77.P370.S2131 - BucketMaintenanceService lifecycle operations

## Scope

- `src/aeat/application/bucket_maintenance/__init__.py`
- `src/aeat/application/bucket_maintenance/_service.py`
- `.vault/adr/2026-05-12-cli-workflow-redesign-adr.md`
- `.vault/adr/2026-05-12-cli-workflow-redesign-bucket-adr.md`
- `.vault/adr/2026-06-03-cli-workflow-redesign-adr.md`

## Description

- Verified the service owns backend/application lifecycle operations, not an operator `config bucket` command group.
- Kept existing `rename`, `delete`, and namespace-level `browse` composition paths.
- Added `export` through the profile portable-bundle serializer, sealed-archive writer, active bucket DEK or recovery passphrase wrap, manifest digest, and `BUCKET_EXPORTED` event emission.
- Added `import_` through the sealed-archive reader, schema/passphrase/collision guards, profile create span, profile bundle deserializer, and `BUCKET_IMPORTED` event emission.
- Recorded search as deferred to the accepted bucket-search ADR instead of implementing a storage-wide scan.

## Outcome

S2131 is complete for W77's service scope. `BucketMaintenanceService` now ships `browse`, `export`, `import`, `rename`, and `delete` as backend/application lifecycle operations; search remains a separate ADR-governed follow-up.

## Checks

- `uv run --no-sync ruff check src/aeat/application/bucket_maintenance src/aeat/adapters/persistence/storage/bucket`
- `uv run --no-sync pytest src/aeat/application/bucket_maintenance/tests src/aeat/adapters/persistence/storage/bucket/tests -m "unit or integration" -q --basetemp Y:/tmp/pytest-w77-bucket-maintenance-full-2`
