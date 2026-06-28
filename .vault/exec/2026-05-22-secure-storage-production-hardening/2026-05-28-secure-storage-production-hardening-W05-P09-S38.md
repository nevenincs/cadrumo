---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-28'
modified: '2026-05-28'
step_id: 'S38'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# `secure-storage-production-hardening` `W05.P09.S38`

Migrated application inventory persistence from the bucket-local JSON file side store to runtime-created secure-object repositories.

- Modified: `src/aeat/application/inventory/_service.py`
- Modified: `src/aeat/application/inventory/test_inventory.py`
- Modified: `src/aeat/adapters/persistence/profile/inventory.py`
- Modified: `src/aeat/adapters/persistence/storage/test_sensitive_persistence_policy.py`
- Created: `.vault/audit/2026-05-28-secure-storage-production-hardening-W05-P09-S38-review.md`

## Description

`InventoryService` no longer reads or writes `aeat_ledgers_dir / "inventory" / <bucket_id>.json`. The service now builds an `InventoryLedgerRepository` through `secure_object_repository_for_bucket(bucket_id, settings)` so inventory reads and writes are governed by the active secure-storage runtime and fail closed on route/session bucket drift.

The profile inventory repository now derives namespace, schema version, default object key, and sensitivity from `PROFILE_INVENTORY_LEDGER_NAMESPACE` instead of duplicating those values locally. The sensitive persistence policy allowlist was tightened by removing the retired evidence-bundle and inventory JSON file writers, and by classifying existing locale CLI YAML writes as non-financial translation-catalogue operations.

The inventory application tests now use real `isolated_runtime_profile` storage instead of a temporary ledger directory. Coverage asserts persistence through the secure-object namespace, active-runtime bucket mismatch refusal, CLI continuity, and runtime-profile isolation without fakes, mocks, stubs, monkeypatches, `skip`, or `xfail`.

## Tests

- `uv run ruff check src/aeat/application/inventory src/aeat/adapters/persistence/profile/inventory.py src/aeat/adapters/persistence/storage/test_sensitive_persistence_policy.py src/aeat/entrypoints/cli/test_inventory_verbs.py`
- `uv run pytest src/aeat/application/inventory/test_inventory.py src/aeat/entrypoints/cli/test_inventory_verbs.py src/aeat/adapters/persistence/profile/test_inventory.py src/aeat/adapters/persistence/profile/test_inventory_roundtrip.py src/aeat/adapters/persistence/storage/test_sensitive_persistence_policy.py::test_sensitive_financial_surfaces_do_not_bypass_secure_object_backend src/aeat/adapters/persistence/storage/test_sensitive_persistence_policy.py::test_production_file_write_inventory_is_reviewed -q`
- `git diff --check -- src/aeat/application/inventory/_service.py src/aeat/application/inventory/test_inventory.py src/aeat/adapters/persistence/profile/inventory.py src/aeat/adapters/persistence/storage/test_sensitive_persistence_policy.py`

Mandatory review was completed in `.vault/audit/2026-05-28-secure-storage-production-hardening-W05-P09-S38-review.md`. The reviewer found no HIGH or CRITICAL issues; both LOW follow-ups were resolved and re-reviewed.
