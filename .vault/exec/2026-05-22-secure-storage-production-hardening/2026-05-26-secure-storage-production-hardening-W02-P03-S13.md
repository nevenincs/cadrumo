---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-26'
modified: '2026-05-26'
step_id: 'S13'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-22-secure-storage-production-hardening-architecture-research]]'
---



# `secure-storage-production-hardening` `W02.P03.S13`

Routed user-profile aggregate secure-object construction through the storage runtime.

- Modified: `src/aeat/application/user_profile/_repository.py`
- Modified: `src/aeat/application/user_profile/_profile_repository.py`
- Modified: `src/aeat/adapters/persistence/storage/runtime.py`
- Modified: `src/aeat/application/user_profile/test_repository.py`
- Created: `.vault/exec/2026-05-22-secure-storage-production-hardening/2026-05-26-secure-storage-production-hardening-W02-P03-S13.md`

## Description

The default user-profile lifecycle and snapshot repositories now obtain their `SecureObjectRepository` through `inspect_bucket_storage_runtime(...).secure_object_repository()` instead of constructing physical secure-object engines directly in the application layer.

`inspect_bucket_storage_runtime` synthesizes a named-bucket settings object when the current settings do not explicitly carry an operator-supplied database URL, so stale derived URLs from an outer settings context do not leak into per-bucket repository routing. Explicit database URL routes remain fail-closed.

The checkpoint also retains the in-flight profile manifest preservation changes in the same user-profile slice: create records the bucket key schedule and save preserves manifest lock, schedule, and unlock metadata instead of rebuilding those fields from defaults.

The tests add runtime-readiness refusal coverage for default lifecycle construction without an active session and keep the real profile repository roundtrip suite green.

## Tests

`uv run ruff check src/aeat/application/user_profile/_repository.py src/aeat/application/user_profile/test_repository.py src/aeat/application/user_profile/test_profile_repository.py src/aeat/adapters/persistence/storage/runtime.py src/aeat/adapters/persistence/storage/test_runtime.py` passed.

`uv run pytest src/aeat/application/user_profile/test_repository.py src/aeat/application/user_profile/test_profile_repository.py src/aeat/adapters/persistence/storage/test_runtime.py -q` reported 41 passed.
