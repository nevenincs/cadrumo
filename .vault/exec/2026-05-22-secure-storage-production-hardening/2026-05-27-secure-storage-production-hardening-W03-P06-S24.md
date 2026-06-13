---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-27'
modified: '2026-05-27'
step_id: 'S24'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-27-secure-storage-production-hardening-w03-p06-s24-review-audit]]'
---

# `secure-storage-production-hardening` `W03.P06.S24`

Required runtime-created secure-object repositories to carry the central namespace registry.

- Modified: `src/aeat/adapters/persistence/storage/sql/secure_objects.py`
- Modified: `src/aeat/adapters/persistence/storage/runtime.py`
- Modified: `src/aeat/adapters/persistence/storage/runtime_repository.py`
- Modified: `src/aeat/adapters/persistence/storage/test_runtime.py`
- Added: `.vault/audit/2026-05-27-secure-storage-production-hardening-W03-P06-S24-review.md`

## Description

`SecureObjectRepository` now accepts and exposes an optional `namespace_registry`. Runtime-owned construction paths pass `STORAGE_NAMESPACE_REGISTRY`, including active-bucket runtime construction, default-route fallback construction before profile selection, and cold-bootstrap construction.

This step carries the registry at construction time only. It intentionally does not enforce namespace sensitivity or schema policy on reads and writes; that remains the owner of W03.P06.S25.

## Tests

Passed:

- `uv run ruff check src/aeat/adapters/persistence/storage/sql/secure_objects.py src/aeat/adapters/persistence/storage/runtime.py src/aeat/adapters/persistence/storage/runtime_repository.py src/aeat/adapters/persistence/storage/test_runtime.py`
- `uv run pytest src/aeat/adapters/persistence/storage/test_runtime.py -q`
- `uv run python -m aeat.locales audit`

Code review found no scoped findings and no remaining HIGH or CRITICAL issues.
