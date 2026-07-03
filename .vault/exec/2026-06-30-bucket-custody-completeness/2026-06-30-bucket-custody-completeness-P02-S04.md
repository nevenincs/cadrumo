---
tags:
  - '#exec'
  - '#bucket-custody-completeness'
date: '2026-06-30'
modified: '2026-06-30'
step_id: 'S04'
related:
  - "[[2026-06-30-bucket-custody-completeness-plan]]"
---

# Add typed CarriedSecureObject and CoverageManifest models

## Scope

- `src/aeat/domain/user_profile/_portable_export.py`

## Description

- Add `CarriedSecureObject` to represent one decrypted secure-object row in the
  v3 bundle contract.
- Carry the stored HMAC lookup digest as canonical base64 because natural object
  keys are not recoverable from the secure-object substrate index.
- Carry arbitrary payload bytes as canonical base64 so full-custody rows are not
  constrained to JSON payloads.
- Add `CoverageManifest` with custody profile, carried namespace set, excluded
  namespace set, and immutable row counts by namespace.
- Keep the new model symbols local to the defining module; no package-level
  re-export surface was added.

## Outcome

P02.S04 is complete. The portable-export schema now has typed v3 contracts for
generic secure-object custody and coverage reporting without constraining later
P03/P04 work to JSON-only payloads.

Verification:

- `uvx vaultspec-rag search "UserProfilePortableExport bundle_schema_version carried_objects coverage_manifest archive schema version" --type code --port 8766 --limit 8`
- `uvx vaultspec-rag search "bucket custody completeness portable export schema coverage manifest carried secure object" --type vault --port 8766 --limit 6`
- `uv run --no-sync pytest src/aeat/domain/user_profile/tests/test_portable_export_schema.py`
- `uv run --no-sync pytest src/aeat/domain/user_profile/tests/test_portable_export_schema.py src/aeat/application/user_profile/tests/test_bundle_schema_versions.py src/aeat/application/bucket_maintenance/tests/test_service_import_export.py src/aeat/application/user_profile/tests/test_bundle_reexports.py src/aeat/adapters/persistence/storage/bucket/tests/test_sealed_archive_roundtrip.py -q`

The schema tests passed with 7 tests. The focused P02 unit/application set
passed with 36 tests.

## Notes

Review corrected two initial schema issues before closure: the carried payload
was changed from JSON text to base64 bytes, and coverage row-count storage was
made actually immutable with `MappingProxyType` after validation.
