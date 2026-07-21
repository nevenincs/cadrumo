---
tags:
  - '#exec'
  - '#bucket-custody-completeness'
date: '2026-06-30'
modified: '2026-06-30'
step_id: 'S05'
related:
  - "[[2026-06-30-bucket-custody-completeness-plan]]"
---

# Bump bundle_schema_version to 3 and add carried_objects and coverage_manifest fields to UserProfilePortableExport

## Scope

- `src/aeat/domain/user_profile/_portable_export.py`

## Description

- Bump `UserProfilePortableExport.bundle_schema_version` from 2 to 3.
- Add `carried_objects` with a default empty tuple.
- Add `coverage_manifest` with a default structured empty manifest.
- Update bundle documentation and CLI roundtrip assertions from v2 to v3.
- Keep current serializer output valid while P03/P04 remain responsible for
  populating carried secure objects and coverage data.

## Outcome

P02.S05 is complete. Current exports now produce v3 bundles that include the
new custody fields, and imports no longer accept the previous v2 contract.

Verification:

- `uv run --no-sync pytest src/aeat/domain/user_profile/tests/test_portable_export_schema.py src/aeat/application/user_profile/tests/test_bundle_schema_versions.py src/aeat/application/bucket_maintenance/tests/test_service_import_export.py src/aeat/application/user_profile/tests/test_bundle_reexports.py src/aeat/adapters/persistence/storage/bucket/tests/test_sealed_archive_roundtrip.py -q`
- `uv run --no-sync pytest -m integration src/aeat/entrypoints/cli/tests/test_profile_export_roundtrip.py`
- `uv run --no-sync ruff check src/aeat/domain/user_profile/_portable_export.py src/aeat/application/user_profile/_bundle.py src/aeat/application/bucket_maintenance/_service.py src/aeat/application/bucket_maintenance/tests/test_service_import_export.py src/aeat/application/user_profile/tests/test_bundle_schema_versions.py src/aeat/domain/user_profile/tests/test_portable_export_schema.py src/aeat/entrypoints/cli/tests/test_profile_export_roundtrip.py src/aeat/adapters/persistence/storage/bucket/tests/test_sealed_archive_roundtrip.py`

The focused P02 unit/application set passed with 36 tests. The real CLI
profile export/import roundtrip passed with 6 integration tests after the
registry path was warmed by the isolated failing node.

## Notes

The CLI integration file transiently hit `MemoryError` while normalising the
legal corpus during calculation registry validation. The exact command then
passed on rerun after the isolated node passed. No P02 code change was made for
that resource-pressure incident.
