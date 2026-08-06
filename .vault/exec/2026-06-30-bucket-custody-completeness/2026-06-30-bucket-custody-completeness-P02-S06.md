---
tags:
  - '#exec'
  - '#bucket-custody-completeness'
date: '2026-06-30'
modified: '2026-07-17'
body_hash: 'sha256:a0a32540a2d65a601422402aa7c590ecd3ee4c5d17eaf7c0427d6a4efc857b59'
step_id: 'S06'
related:
  - "[[2026-06-30-bucket-custody-completeness-plan]]"
---

# Bump _ARCHIVE_SCHEMA_VERSION to 2 and narrow SUPPORTED_BUNDLE_SCHEMA_VERSIONS to the single current version, deleting old-shape tolerance

## Scope

- `src/aeat/application/bucket_maintenance/_service.py`

## Description

- Bump `_ARCHIVE_SCHEMA_VERSION` from 1 to 2 for sealed bucket archives.
- Narrow `SUPPORTED_BUNDLE_SCHEMA_VERSIONS` to `frozenset({3})`.
- Remove explicit v2 construction from the serializer so current exports use the
  v3 model default.
- Reject schema-1 archives before decrypting payload bytes.
- Reject schema-2 bundle payloads immediately after decrypt/parse and before
  filing-baseline validation or bucket provisioning.
- Update service tests to assert archive schema 2 export events and old-shape
  refusal with no restored bucket pointer.

## Outcome

P02.S06 is complete. The sealed archive wrapper is now version 2, the portable
bundle import gate accepts only v3, and obsolete inner bundle versions fail
closed before any import side effects.

Verification:

- `uvx vaultspec-rag search "BucketMaintenanceService _ARCHIVE_SCHEMA_VERSION SUPPORTED_BUNDLE_SCHEMA_VERSIONS import export archive schema" --type code --port 8766 --limit 8`
- `uv run --no-sync pytest src/aeat/application/bucket_maintenance/tests/test_service_import_export.py -q`
- `uv run --no-sync pytest src/aeat/domain/user_profile/tests/test_portable_export_schema.py src/aeat/application/user_profile/tests/test_bundle_schema_versions.py src/aeat/application/bucket_maintenance/tests/test_service_import_export.py src/aeat/application/user_profile/tests/test_bundle_reexports.py src/aeat/adapters/persistence/storage/bucket/tests/test_sealed_archive_roundtrip.py -q`
- `uv run --no-sync ruff check src/aeat/domain/user_profile/_portable_export.py src/aeat/application/user_profile/_bundle.py src/aeat/application/bucket_maintenance/_service.py src/aeat/application/bucket_maintenance/tests/test_service_import_export.py src/aeat/application/user_profile/tests/test_bundle_schema_versions.py src/aeat/domain/user_profile/tests/test_portable_export_schema.py src/aeat/entrypoints/cli/tests/test_profile_export_roundtrip.py src/aeat/adapters/persistence/storage/bucket/tests/test_sealed_archive_roundtrip.py`
- `git diff --check -- src/aeat/domain/user_profile/_portable_export.py src/aeat/application/user_profile/_bundle.py src/aeat/application/bucket_maintenance/_service.py src/aeat/application/bucket_maintenance/tests/test_service_import_export.py src/aeat/application/user_profile/tests/test_bundle_schema_versions.py src/aeat/domain/user_profile/tests/test_portable_export_schema.py src/aeat/entrypoints/cli/tests/test_profile_export_roundtrip.py src/aeat/adapters/persistence/storage/bucket/tests/test_sealed_archive_roundtrip.py`

The service import/export test file passed with 9 tests. The focused P02
unit/application set passed with 36 tests. Ruff and diff whitespace checks
passed.

## Notes

The independent review found one HIGH issue: sealed import originally parsed a
schema-2 bundle and could run filing-baseline validation or provision a bucket
before `deserialize_profile_bundle` rejected the old version. The fix adds the
service-level bundle-version gate immediately after payload parsing, with a
regression archive that carries a valid schema-2 bundle inside a current
schema-2 archive and asserts no bucket pointer is created.
