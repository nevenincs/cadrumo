---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-27'
modified: '2026-05-27'
step_id: 'S86'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---



# `secure-storage-production-hardening` `W12.P21.S86` Attachment Runtime-Default Slice

Closed the `AFR-050` attachment-store runtime-default slice without touching concurrent workflow, modelo, CLI, or locale worktree changes.

## Changes

- Migrated `AttachmentStore` default object repository resolution from direct `SecureObjectRepository()` construction to `secure_object_repository_for_active_bucket()`.
- Preserved explicit `objects=` injection for tests and callers that already own a secure-object repository.
- Kept attachment blobs and manifests in the existing encrypted secure-object namespaces without changing payload schema, sensitivity class, or content-addressed identifiers.

## Validation

- `uv run pytest src/aeat/adapters/persistence/storage/test_attachment_store_roundtrip.py src/aeat/domain/attachments/test_repository.py src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py::test_attachment_store_default_isolates_active_profile_writes src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py::test_migrated_runtime_defaults_refuse_missing_session -k attachment src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py::test_migrated_runtime_defaults_refuse_route_session_mismatch -k attachment src/aeat/adapters/persistence/storage/test_runtime.py::test_runtime_creates_bucket_attached_secure_object_repository src/aeat/adapters/persistence/storage/test_runtime.py::test_runtime_repository_factory_refuses_unready_runtime -q` - 8 passed, 66 deselected.
- `uv run ruff check src/aeat/adapters/persistence/storage/attachment.py src/aeat/adapters/persistence/storage/test_attachment_store_roundtrip.py src/aeat/domain/attachments/test_repository.py src/aeat/adapters/persistence/storage/test_runtime.py` - passed.
- `rg -n "SecureObjectRepository\\(" src/aeat/adapters/persistence/storage/attachment.py` - no remaining direct constructor hits in the attachment store.

## Residual Debt

- The broad migrated-runtime parameterized gate remains red on unrelated repositories that still do not consistently surface `StorageValidationError` for missing or mismatched active sessions.
- The production direct-construction guard still reports broader pre-existing direct `SecureObjectRepository` use outside this slice.
- `test_runtime_migrated_repositories.py` has a pre-existing import ordering ruff issue when that whole file is included in a lint target; this slice did not edit that file.
- `S86` remains open because it owns multiple adapter runtime-default surfaces. This record closes only the `AFR-050` attachment-store increment.

## Tracking

Completed internal tasklist for this slice:

- Identify non-dirty runtime-default adapter target: complete.
- Migrate attachment default repository resolution to runtime-owned factory: complete.
- Verify active-profile isolation, missing-session refusal, and route-mismatch refusal for attachment defaults: complete.
- Complete code-review pass: complete.
- Persist slice evidence: complete.
