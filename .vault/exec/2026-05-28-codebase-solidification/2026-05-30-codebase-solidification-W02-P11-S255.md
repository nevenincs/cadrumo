---
step_id: S255
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-30
modified: '2026-05-30'
agent: coder-lambda6
commit: 590e07cc1
status: closed
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# codebase-solidification W02.P11.S255

Migrated 4 bare raises in `_manifest.py` to `BucketValidationError`:
- `ManifestKdfParams._check_salt_length` (ValueError → BucketValidationError)
- `ManifestKdfParams._decode_salt` (TypeError → BucketValidationError)
- `BucketManifest._coerce_status` (TypeError → BucketValidationError)
- `BucketManifest._coerce_key_schedule` (TypeError → BucketValidationError)

`BucketValidationError(BucketError, ValueError)` introduced in `_errors.py`; registered in `_adapters.py` as `INTEGRITY_STORAGE_BUCKET_VALIDATION`; locale key added to en/es/ca/hu.
