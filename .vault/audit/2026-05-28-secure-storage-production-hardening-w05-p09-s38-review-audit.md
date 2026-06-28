---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# `secure-storage-production-hardening` Code Review

Review scope: `W05.P09.S38` inventory persistence migration. Audited `src/aeat/application/inventory/_service.py`, `src/aeat/application/inventory/test_inventory.py`, `src/aeat/adapters/persistence/profile/inventory.py`, and `src/aeat/adapters/persistence/storage/test_sensitive_persistence_policy.py` against secure-storage routing correctness, runtime bucket semantics, plaintext side-store removal, settings centralization, exception/logging risks, and test discipline.

No HIGH or CRITICAL issues found.

Delta re-review on 2026-05-28: both previously recorded LOW follow-ups are resolved. No remaining findings were identified in the re-reviewed delta.

S38-001 | LOW | RESOLVED | Add an application-level mismatch test for runtime bucket refusal

`InventoryService` now resolves `InventoryLedgerRepository` through `secure_object_repository_for_bucket(bucket_id, settings)`, and the storage runtime rejects route/session bucket drift. The current `TestBucketIsolation` coverage proves separate runtime profiles do not share ledgers, but it does not directly assert that one active runtime refuses an inventory operation for a different requested bucket id. Add a real-behavior test using `isolated_runtime_profile` that calls an inventory verb with a non-active bucket id and expects the storage runtime refusal, without fakes, mocks, monkeypatches, `skip`, or `xfail`.

Resolution: `src/aeat/application/inventory/test_inventory.py` now includes `test_requested_bucket_must_match_active_runtime`, which uses the real `isolated_runtime_profile` setup and asserts that a non-active requested bucket id raises `StorageValidationError`.

S38-002 | LOW | RESOLVED | Route inventory repository sensitivity through the namespace definition

`src/aeat/adapters/persistence/profile/inventory.py` centralizes namespace, object key, and schema version through `PROFILE_INVENTORY_LEDGER_NAMESPACE`, but read/write calls still spell the classification as `SensitivityClass.FINANCIAL`. The current value matches the registry, so this is not a runtime failure. For registry-authority consistency, use `PROFILE_INVENTORY_LEDGER_NAMESPACE.sensitivity` for both `expected_class` and `classification`.

Resolution: `src/aeat/adapters/persistence/profile/inventory.py` now derives `_INVENTORY_SENSITIVITY` from `PROFILE_INVENTORY_LEDGER_NAMESPACE.sensitivity` and uses it for secure-object reads and writes.

Verification performed:

- `uv run pytest src/aeat/application/inventory/test_inventory.py src/aeat/adapters/persistence/storage/test_sensitive_persistence_policy.py` passed: 22 tests.
- `uv run pytest src/aeat/adapters/persistence/profile/test_inventory.py src/aeat/adapters/persistence/profile/test_inventory_roundtrip.py` passed: 5 tests.
- `uv run ruff check src/aeat/application/inventory/_service.py src/aeat/application/inventory/test_inventory.py src/aeat/adapters/persistence/profile/inventory.py src/aeat/adapters/persistence/storage/test_sensitive_persistence_policy.py` passed.

Delta verification performed:

- `uv run ruff check src/aeat/adapters/persistence/profile/inventory.py src/aeat/application/inventory/test_inventory.py src/aeat/application/inventory/_service.py src/aeat/adapters/persistence/storage/test_sensitive_persistence_policy.py` passed.
- `uv run pytest src/aeat/application/inventory/test_inventory.py src/aeat/adapters/persistence/storage/test_sensitive_persistence_policy.py src/aeat/adapters/persistence/profile/test_inventory.py src/aeat/adapters/persistence/profile/test_inventory_roundtrip.py` passed: 28 tests.
- `git diff --check -- src/aeat/adapters/persistence/profile/inventory.py src/aeat/application/inventory/test_inventory.py .vault/audit/2026-05-28-secure-storage-production-hardening-W05-P09-S38-review.md` passed with only the existing CRLF normalization warning for `src/aeat/application/inventory/test_inventory.py`.

Review notes:

- The prior `aeat_ledgers_dir / "inventory" / <bucket>.json` plaintext inventory side store was removed from the service and from the production file-write allowlist.
- The service uses settings-backed runtime repository construction and does not introduce direct environment access.
- The scoped tests use the real secure SQL runtime helper and do not introduce fake, stub, mock, monkeypatch, `skip`, or `xfail` shortcuts.
- Scoped logging does not include plaintext ledger contents; the repository save log reports only ledger count and logical object key.
