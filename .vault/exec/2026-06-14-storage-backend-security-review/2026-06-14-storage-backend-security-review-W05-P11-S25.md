---
tags:
  - '#exec'
  - '#storage-backend-security-review'
date: '2026-06-15'
modified: '2026-06-15'
step_id: 'S25'
related:
  - "[[2026-06-14-storage-backend-security-review-plan]]"
---




# Promote the sealed-archive read and write helpers to the bucket package all and rebind the maintenance service call sites

## Scope

- `src/aeat/adapters/persistence/storage/bucket/__init__.py`

## Description


- Promote `write_sealed_archive`, `read_sealed_archive`, and `SealedArchiveContents` to the bucket package `__all__` (eager re-export; the sealed-archive modules import only stdlib plus the already-imported `_export_header`, so the surface stays import-light).
- Rebind the `BucketMaintenanceService` export call site to import `write_sealed_archive` through the package surface (folded into the existing `from ...storage.bucket import ...` block) instead of the private `bucket._sealed_archive_writer` submodule.
- Rebind the service import call site to `from ...storage.bucket import read_sealed_archive` instead of the private `bucket._sealed_archive_reader` submodule.
- Rebind the application-layer test (`test_service_import_export`) to the package surface. Adapter-internal tests keep their intra-package sibling imports.

## Outcome

Closes the `service-imports-via-top-level-reexports` violation for the sealed-archive helpers: the application-layer `BucketMaintenanceService` no longer dots into the bucket package's private submodules. Lint clean; the sealed-archive roundtrip suite, the service import/export suite, and both `user_profile` lazy-boundary gates plus the CLI lazy-command-tree gate pass (18 passed). Committed as `refactor(bucket-adapter): promote sealed-archive read/write helpers to bucket package surface (S25)`.

## Notes


None. The promoted symbols carry no extra eager-import weight, so json-pipe-safety is unaffected (lazy-boundary gates green).
