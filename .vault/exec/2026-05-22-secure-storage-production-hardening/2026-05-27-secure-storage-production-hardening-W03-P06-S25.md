---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-27'
modified: '2026-05-27'
step_id: 'S25'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-27-secure-storage-production-hardening-w03-p06-s25-review-audit]]'
---

# `secure-storage-production-hardening` `W03.P06.S25`

Enforced registered sensitivity and schema policy on runtime-bound secure-object reads and writes.

- Modified: `src/aeat/adapters/persistence/storage/_namespace_registry.py`
- Modified: `src/aeat/adapters/persistence/storage/sql/secure_objects.py`
- Modified: `src/aeat/adapters/persistence/storage/sql/test_secure_objects.py`
- Modified: `src/aeat/adapters/persistence/storage/test_runtime.py`
- Modified: `src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py`
- Added: `.vault/audit/2026-05-27-secure-storage-production-hardening-W03-P06-S25-review.md`

## Description

`StorageHierarchyRegistry` now supports lookup by persisted namespace value. `SecureObjectRepository` uses that lookup when a namespace registry is bound, which is the runtime-owned path introduced by W03.P06.S24.

The repository now refuses unregistered namespaces, sensitivity mismatches, and schema mismatches on writes. It also refuses reads where the caller's expected sensitivity conflicts with the registry or where a stored row is newer than the registered namespace schema. Direct unbound repositories retain legacy behavior for tests and bootstrap-only scenarios.

`iter_all_records_raw`, integrity probes, quarantine, `list_namespaces`, `list_keys`, `exists`, and `peek_metadata` were intentionally left as metadata, repair, or mirror surfaces. Repair ownership remains W03.P06.S26 and registry completeness remains W03.P06.S27.

## Tests

Passed:

- `uv run ruff check src/aeat/adapters/persistence/storage/_namespace_registry.py src/aeat/adapters/persistence/storage/sql/secure_objects.py src/aeat/adapters/persistence/storage/sql/test_secure_objects.py src/aeat/adapters/persistence/storage/test_runtime.py src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py`
- `uv run pytest src/aeat/adapters/persistence/storage/sql/test_secure_objects.py src/aeat/adapters/persistence/storage/test_runtime.py -q`
- `uv run pytest src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py -q`
- `uv run pytest src/aeat/adapters/persistence/storage/test_hardening_convention_guards.py src/aeat/application/test_namespace_registry_adoption.py -q`
- `uv run python -m aeat.locales audit`

Code review found no scoped findings and no remaining HIGH or CRITICAL issues.
