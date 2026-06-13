---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-27'
modified: '2026-05-27'
step_id: 'S27'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-27-secure-storage-production-hardening-w03-p06-s27-review-audit]]'
---

# `secure-storage-production-hardening` `W03.P06.S27`

Added registry completeness tests for discovered secure-object namespaces.

- Modified: `src/aeat/adapters/persistence/storage/test_namespace_registry.py`
- Added: `.vault/audit/2026-05-27-secure-storage-production-hardening-W03-P06-S27-review.md`

## Description

`test_every_discovered_production_secure_object_namespace_is_registered` now statically scans production `src/aeat` sources for secure-object namespace usage and fails when a discovered namespace is absent from `STORAGE_NAMESPACE_REGISTRY`.

The scanner intentionally excludes tests, test helper packages, and `_namespace_registry.py` so it does not prove the registry by reading the registry. It discovers namespace values from production namespace assignments, registry-derived namespace attributes, secure-object repository calls, and `SecureBoundRepository` construction.

The guard currently discovers 42 production secure-object namespaces and confirms every discovered value is registered.

## Tests

Passed:

- `uv run ruff check src/aeat/adapters/persistence/storage/test_namespace_registry.py`
- `uv run pytest src/aeat/adapters/persistence/storage/test_namespace_registry.py src/aeat/application/test_namespace_registry_adoption.py src/aeat/adapters/persistence/storage/test_hardening_convention_guards.py -q`
- `uv run pytest src/aeat/adapters/persistence/storage/test_runtime.py src/aeat/adapters/persistence/storage/sql/test_secure_objects.py -q`
- `uv run python -m aeat.locales audit`

Code review found and verified fixes for one HIGH scanner false-negative risk and one MEDIUM tautology risk. No HIGH or CRITICAL issues remain.
