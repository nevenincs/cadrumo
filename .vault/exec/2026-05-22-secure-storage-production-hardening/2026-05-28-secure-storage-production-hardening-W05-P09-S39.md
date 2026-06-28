---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-28'
modified: '2026-05-28'
step_id: 'S39'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-28-secure-storage-production-hardening-w05-p09-s39-review-audit]]'
---



# `secure-storage-production-hardening` `W05.P09.S39`

Closed the live snapshot side-store migration row after confirming the live
verify, expedientes, and notifications persistence paths now route through
runtime-created secure-object repositories.

- Modified: `src/aeat/adapters/persistence/storage/__init__.py`
- Modified: `src/aeat/adapters/persistence/storage/test_namespace_registry.py`
- Modified: `src/aeat/adapters/persistence/storage/test_sensitive_persistence_policy.py`
- Modified: `src/aeat/application/_storage_paths.py`
- Modified: `src/aeat/application/test_storage_paths.py`
- Created: `.vault/audit/2026-05-28-secure-storage-production-hardening-W05-P09-S39-review.md`

## Description

S39 implementation is present in the live application services: live verify
observations, expedientes snapshots, and notification snapshots construct their
repositories through runtime bucket storage and registered secure-object
namespaces. The remaining closeout removed stale policy allowlist entries for
the former live JSONL writers and trimmed shared `storage_path` tests so they no
longer assert retired evidence, inventory, or live side-store layouts.

The namespace export and registry tests were kept aligned with the registered
live secure-object namespaces used by the migrated services.

The mandatory review reported no HIGH or CRITICAL issues. It recorded one
MEDIUM follow-up for fail-closed list behavior on semantic bucket mismatches and
one LOW documentation/comment cleanup follow-up. Both remain in the review
record for the W16 observation-pool adoption path and are not blockers for S39
closure.

## Tests

- `uv run ruff check src/aeat/application/_storage_paths.py src/aeat/application/test_storage_paths.py src/aeat/application/live/_verify.py src/aeat/application/live/_snapshot_base.py src/aeat/application/live/_expedientes.py src/aeat/application/live/_notifications.py src/aeat/application/live/test_verify.py src/aeat/application/live/test_expedientes.py src/aeat/application/live/test_notifications.py src/aeat/entrypoints/cli/test_live_read_subgroups.py src/aeat/entrypoints/cli/test_live_notifications_verbs.py src/aeat/adapters/persistence/storage/_namespace_registry.py src/aeat/adapters/persistence/storage/__init__.py src/aeat/adapters/persistence/storage/test_namespace_registry.py src/aeat/adapters/persistence/storage/test_sensitive_persistence_policy.py`
- `uv run pytest src/aeat/application/live/test_verify.py src/aeat/application/live/test_expedientes.py src/aeat/application/live/test_notifications.py src/aeat/application/test_storage_paths.py src/aeat/entrypoints/cli/test_live_read_subgroups.py src/aeat/entrypoints/cli/test_live_notifications_verbs.py src/aeat/adapters/persistence/storage/test_namespace_registry.py::test_w03_s22_auth_session_cache_remote_namespaces_are_registered src/aeat/adapters/persistence/storage/test_namespace_registry.py::test_w03_s22_namespace_registration_coverage_is_present src/aeat/adapters/persistence/storage/test_namespace_registry.py::test_every_discovered_production_secure_object_namespace_is_registered src/aeat/adapters/persistence/storage/test_sensitive_persistence_policy.py::test_sensitive_financial_surfaces_do_not_bypass_secure_object_backend src/aeat/adapters/persistence/storage/test_sensitive_persistence_policy.py::test_production_file_write_inventory_is_reviewed -q`
- `uv run pytest src/aeat/application/live/test_verify.py src/aeat/application/live/test_expedientes.py src/aeat/application/live/test_notifications.py src/aeat/entrypoints/cli/test_live_notifications_verbs.py src/aeat/entrypoints/cli/test_live_read_subgroups.py src/aeat/adapters/persistence/storage/test_sensitive_persistence_policy.py src/aeat/adapters/persistence/storage/test_namespace_registry.py src/aeat/application/test_storage_paths.py -q`
- `git diff --check -- src/aeat/application/_storage_paths.py src/aeat/application/test_storage_paths.py src/aeat/application/live/_verify.py src/aeat/application/live/_snapshot_base.py src/aeat/application/live/_expedientes.py src/aeat/application/live/_notifications.py src/aeat/application/live/test_verify.py src/aeat/application/live/test_expedientes.py src/aeat/application/live/test_notifications.py src/aeat/entrypoints/cli/test_live_read_subgroups.py src/aeat/entrypoints/cli/test_live_notifications_verbs.py src/aeat/adapters/persistence/storage/_namespace_registry.py src/aeat/adapters/persistence/storage/__init__.py src/aeat/adapters/persistence/storage/test_namespace_registry.py src/aeat/adapters/persistence/storage/test_sensitive_persistence_policy.py .vault/audit/2026-05-27-secure-storage-hierarchy-namespace-inventory.md`

Review audit: `2026-05-28-secure-storage-production-hardening-W05-P09-S39-review`.
