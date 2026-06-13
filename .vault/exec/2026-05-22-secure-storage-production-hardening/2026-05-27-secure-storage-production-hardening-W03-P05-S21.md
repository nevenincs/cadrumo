---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-27'
modified: '2026-05-27'
step_id: 'S21'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# `secure-storage-production-hardening` `W03.P05.S21`

Registered the remaining profile ledger namespace contracts required for the profile, ledger, invoice, filing, wallet, and calculation namespace set.

- Modified: `src/aeat/adapters/persistence/storage/_namespace_registry.py`
- Modified: `src/aeat/adapters/persistence/storage/__init__.py`
- Modified: `src/aeat/adapters/persistence/storage/test_namespace_registry.py`
- Modified: `.vault/audit/2026-05-27-secure-storage-hierarchy-namespace-inventory.md`
- Modified: `.vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md`

## Description

W15.P33 had already registered invoice, filing, wallet, calculation, and ledger classification namespace definitions, but discovery showed that profile-local inventory and asset ledgers were still missing from the central registry.

This step adds registry definitions for:

- `profile_inventory_ledger` using namespace `aeat.persistence.profile.inventory`.
- `profile_assets_ledger` using namespace `aeat.persistence.profile.assets`.
- `profile_assets_amortization_ledger` using namespace `aeat.persistence.profile.assets.amortization`.

Each profile ledger namespace is financial, schema version 1, bucket-local, and has the named singleton object key `default` through `SECURE_OBJECT_DEFAULT_KEY`. The storage package exports the new registry definitions so later S23 consumption work can replace local constants in profile persistence modules without importing registry internals.

The same touched registry/export files also carried the intersecting live IVA remote-state acquisition namespace registration discovered during the S20 inventory review. That registry entry remains included in the storage exports and inventory table in this commit because it shares the same central registry surface.

The namespace registry tests now assert the W03.P05.S21 coverage set and validate the three profile ledger definitions through registry lookup.

## Tests

Passed:

- `uv run ruff check src/aeat/adapters/persistence/storage/_namespace_registry.py src/aeat/adapters/persistence/storage/__init__.py src/aeat/adapters/persistence/storage/test_namespace_registry.py`
- `uv run pytest -q src/aeat/adapters/persistence/storage/test_namespace_registry.py`
- `uv run ruff check src/aeat/adapters/persistence/storage/_namespace_registry.py src/aeat/adapters/persistence/storage/__init__.py src/aeat/adapters/persistence/storage/test_namespace_registry.py src/aeat/adapters/persistence/profile/inventory.py src/aeat/adapters/persistence/profile/assets.py`
- `uv run pytest -q src/aeat/adapters/persistence/profile/test_inventory.py src/aeat/adapters/persistence/profile/test_assets.py src/aeat/adapters/persistence/storage/test_namespace_registry.py`
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md`
