---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S2145'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
---

# W77.P373.S2145 - BucketMaintenanceService service-contract tests

## Scope

- `src/aeat/application/bucket_maintenance/tests/test_manifest_digest.py`
- `src/aeat/application/bucket_maintenance/tests/test_service_browse.py`
- `src/aeat/application/bucket_maintenance/tests/test_service_delete.py`
- `src/aeat/application/bucket_maintenance/tests/test_service_import_export.py`
- `src/aeat/application/bucket_maintenance/tests/test_service_rename.py`
- `src/aeat/adapters/persistence/storage/bucket/tests/`

## Description

- Added real-behavior export/import service-contract coverage using isolated real profile storage, real `ProfileLifecycleService`, real sealed archive writer/reader, real crypto, and real bucket-event history.
- Verified export writes an encrypted archive, includes the recovery-wrap path when requested, and emits `BUCKET_EXPORTED`.
- Verified import provisions a fresh bucket from a recovery archive and emits `BUCKET_IMPORTED`.
- Verified import refuses missing recovery passphrase and live bucket collision without force.
- Re-ran the existing browse/delete/rename/manifest digest service tests and sealed-archive adapter suite.

## Outcome

S2145 is complete. The bucket-maintenance service paths are covered by real service/application behavior, not fakes, mocks, stubs, monkeypatches, skips, or xfail shortcuts.

## Checks

- `uv run --no-sync pytest src/aeat/application/bucket_maintenance/tests src/aeat/adapters/persistence/storage/bucket/tests -m "unit or integration" -q --basetemp Y:/tmp/pytest-w77-bucket-maintenance-full-2` (127 passed)
