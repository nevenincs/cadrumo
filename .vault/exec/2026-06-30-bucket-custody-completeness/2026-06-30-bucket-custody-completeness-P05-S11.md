---
tags:
  - '#exec'
  - '#bucket-custody-completeness'
date: '2026-06-30'
modified: '2026-06-30'
step_id: 'S11'
related:
  - "[[2026-06-30-bucket-custody-completeness-plan]]"
---

# Wire BucketMaintenanceService export and import_ to the full custody profile and verify coverage on import

## Scope

- `src/aeat/application/bucket_maintenance/_service.py`

## Description

- Wire sealed bucket export to `StorageCustodyProfile.FULL`.
- Keep the archive payload AEAD-sealed and enforce coverage before writing the archive.
- Validate bundle schema immediately after decrypting a sealed archive and before provisioning or baseline validation.
- Harden bucket maintenance service imports to source modules for storage, archive, crypto, workflow, and bucket event owners.

## Outcome

- Complete. Sealed archive is the full-custody recovery transport and rejects unsupported inner bundle versions before target mutation.
- Verified by `test_service_import_export.py`, `test_custody_completeness.py`, ruff, and reviewer pass.

## Notes

- Feature-scoped vault check is clean except for known global feature-rename-integrity drift outside this feature.
