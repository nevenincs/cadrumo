---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-26'
modified: '2026-05-26'
step_id: 'S12'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-22-secure-storage-production-hardening-architecture-research]]'
---



# `secure-storage-production-hardening` `W02.P03.S12`

Added bucket-attached secure-object repository factory methods to the storage runtime.

- Modified: `src/aeat/adapters/persistence/storage/runtime.py`
- Modified: `src/aeat/adapters/persistence/storage/test_runtime.py`
- Created: `.vault/exec/2026-05-22-secure-storage-production-hardening/2026-05-26-secure-storage-production-hardening-W02-P03-S12.md`

## Description

`StorageRuntime` now exposes `require_ready()` and `secure_object_repository()`. The factory refuses unready runtime states before repository construction, derives bucket-attached settings from the ready runtime state, and returns a `SecureObjectRepository` bound to the active bucket database.

The runtime keeps storage root and bucket id excluded from model dumps and repr output, preserving the redacted diagnostics contract while still allowing trusted factory methods to build the correct repository. The tests cover no-session refusal, route and session mismatch, unsecured backend refusal, path-redaction, and a real secure-object save/load roundtrip through the runtime factory.

## Tests

`uv run ruff check src/aeat/adapters/persistence/storage/runtime.py src/aeat/adapters/persistence/storage/test_runtime.py src/aeat/adapters/persistence/storage/__init__.py` passed.

`uv run pytest src/aeat/adapters/persistence/storage/test_runtime.py -q` reported 10 passed.

`uv run pytest src/aeat/adapters/persistence/storage/test_runtime.py src/aeat/adapters/persistence/storage/sql/test_secure_objects.py -q` reported 37 passed.

`uv run python -c "from aeat.adapters.persistence.storage.runtime import StorageRuntime; print(hasattr(StorageRuntime, 'secure_object_repository'), hasattr(StorageRuntime, 'require_ready'))"` returned `True True`.
