---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:ba21ffc02e4fa8d48475cb5582343defc78de3bcca176a9e7fa30890605087d5'
step_id: 'S70'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---

# Replace persistence session, bucket-lock, KEK, master-key, and secure-object login guidance with exact boundary-owned canonical login or typed storage no-recovery outcomes

## Scope

- `src/cadrumo/adapters/persistence/storage/bucket/_errors.py`
- `src/cadrumo/adapters/persistence/storage/master_key`
- `src/cadrumo/adapters/persistence/storage/errors.py`
- `src/cadrumo/adapters/persistence/storage/sql/secure_objects.py`
- `src/cadrumo/adapters/persistence/storage/sql/tests`
- `src/cadrumo/entrypoints/cli/_errors.py`
- `src/cadrumo/entrypoints/cli/tests/test_session_lifecycle_roundtrip.py`
- `src/cadrumo/entrypoints/cli/tests/test_error_boundary_integration.py`
- `src/cadrumo/entrypoints/cli/tests/test_storage_session_preconditions.py`
- `src/cadrumo/application/operator_actions`

## Description

- Replace raw storage login/profile-list guidance with typed persistence facts and exact storage condition identities.
- Centralise all seven locked-bucket raises behind the `BucketLockedError` contract.
- Offer canonical profile login only when the public profile label is resolvable; otherwise emit an explicit no-action outcome.
- Pin the producer census, fact polarity, SQLAlchemy unwrapping, public-label binding, and no-recovery contracts.

## Outcome

Production commit `b54efc44ea`, import-only follow-up `747518da43`, and proof alignment commit `f781bceba7` complete the storage-session migration. Six exact storage conditions cover the five persistence producer families plus locked buckets. Bucket identifiers are never substituted for public profile names, and persistence code owns no application action policy.

VaultSpec RAG and independent review found no action, verdict, or catalogue redeclaration and no remaining login/profile-list production prose. Ruff passes and the focused closure suite passes 38 tests with three marker-deselected cases.

## Notes

- Keychain silent-resume failure remains classified as an environmental failure rather than an operator recovery action.
