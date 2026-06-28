---
tags: ["#exec", "#secure-storage-production-hardening"]
date: "2026-05-26"
modified: '2026-05-26'
step_id: "S13"
related:
  - "[[2026-05-22-secure-storage-production-hardening-refactor-plan]]"
---

# `secure-storage-production-hardening` `W02.P03.S13`

Routed profile aggregate repositories through the storage runtime.

- Modified: `src/aeat/application/user_profile/_repository.py`
- Modified: `src/aeat/application/user_profile/test_repository.py`
- Modified: `src/aeat/adapters/persistence/storage/runtime.py`
- Modified: `src/aeat/adapters/persistence/storage/__init__.py`
- Modified: `src/aeat/adapters/persistence/storage/test_runtime.py`
- Modified: `.vault/audit/2026-05-22-secure-storage-production-hardening-W02-P03-review.md`

## Description

Default user-profile lifecycle and snapshot repository construction now resolves bucket-attached secure-object storage through `inspect_bucket_storage_runtime(...).secure_object_repository()` instead of manually constructing a bucket SQLite URL. The runtime helper preserves the explicit database URL guard: if live settings carry `aeat_database_url`, the named-bucket runtime reports the explicit route as unready rather than hiding it behind a synthesized bucket route.

The storage runtime still supports legitimate named-bucket construction when no explicit database URL is present. This keeps cross-bucket profile reads and writes attached to the requested bucket database while enrolling the aggregate repository path in the runtime readiness contract.

## Tests

Validated with:

- `uv run --no-sync pytest src/aeat/adapters/persistence/storage/test_runtime.py src/aeat/application/user_profile/test_repository.py src/aeat/application/user_profile/test_profile_repository.py -q`
- `uv run --no-sync ruff check src/aeat/adapters/persistence/storage/runtime.py src/aeat/adapters/persistence/storage/test_runtime.py src/aeat/adapters/persistence/storage/__init__.py src/aeat/application/user_profile/_repository.py src/aeat/application/user_profile/test_repository.py src/aeat/application/user_profile/test_profile_repository.py`

Code review persisted in `.vault/audit/2026-05-22-secure-storage-production-hardening-W02-P03-review.md`.
