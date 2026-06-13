---
tags: ["#exec", "#secure-storage-production-hardening"]
date: "2026-05-26"
modified: '2026-05-26'
step_id: "S12"
related:
  - "[[2026-05-22-secure-storage-production-hardening-refactor-plan]]"
---

# `secure-storage-production-hardening` `W02.P03.S12`

Added a bucket-attached secure-object repository factory to the storage runtime.

- Modified: `src/aeat/adapters/persistence/storage/runtime.py`
- Modified: `src/aeat/adapters/persistence/storage/test_runtime.py`
- Created: `.vault/audit/2026-05-22-secure-storage-production-hardening-W02-P03-review.md`

## Description

Added `StorageRuntime.require_ready()` and `StorageRuntime.secure_object_repository()` so callers can construct a secure-object repository through a ready runtime rather than rebuilding physical database routes locally. The factory rebuilds the bucket-scoped settings route from the runtime's internal root and bucket id while preserving redacted public diagnostics.

Repository construction rechecks the live active session immediately before creating the engine. It refuses stale snapshots where the session is missing, sealed, expired, unsecured, or switched to another bucket, so the runtime cannot be inspected once and reused after custody state has drifted.

## Tests

Validated with:

- `uv run --no-sync pytest src/aeat/adapters/persistence/storage/test_runtime.py src/aeat/core/test_storage_route_classification.py -q`
- `uv run --no-sync ruff check src/aeat/adapters/persistence/storage/runtime.py src/aeat/adapters/persistence/storage/test_runtime.py src/aeat/adapters/persistence/storage/__init__.py`

Code review persisted in `.vault/audit/2026-05-22-secure-storage-production-hardening-W02-P03-review.md`.
