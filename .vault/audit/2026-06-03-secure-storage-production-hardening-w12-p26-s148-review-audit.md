---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
modified: '2026-06-03'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-03-secure-storage-production-hardening-W12-P26-S148]]'
---

# `secure-storage-production-hardening` `W12.P26.S148` Review

## S148-001 | PASS | `retired` target was corrected

The plan listed `src/aeat/adapters/persistence/profile/inventory.py` with target `retired`, but the file is active production code. `aeat.application.inventory._service` imports `InventoryLedgerRepository`, and runtime migration tests cover `load_inventory()` and `save_inventory()`.

Resolution: the plan target for `AFR-046` / `W12.P26.S148` is corrected to `runtime-default`. The file was hardened rather than deleted.

## S148-002 | PASS | Inventory repository remains on registered secure-object storage

The repository persists `InventoryLedgerDocument` through `SecureObjectRepository` under `PROFILE_INVENTORY_LEDGER_NAMESPACE`, which is FINANCIAL-class and bucket-local.

Resolution: the implementation continues to derive namespace, sensitivity, schema version, and singleton object key from the registered namespace definition.

## S148-003 | PASS | Logical SQL path and encoding conventions are centralized

The repository previously constructed `Path("db://secure_objects")` directly and used raw UTF-8 literals for JSON bytes. The inventory corruption test used the same raw encoding literal.

Resolution: logical markers now use `secure_object_logical_path()` and JSON byte conversions use `UTF_8_ENCODING`.

## S148-004 | PASS | Inventory errors are localized and observable

Load failures, duplicate ledger refusals, duplicate movement refusals, and missing ledger refusals previously carried raw English messages only. Load failures wrapped lower-level errors without debug evidence.

Resolution: those errors now carry `translated_message` keys and structured context. Load wrappers emit sanitized debug entries with namespace, object key, and error type before raising `InventoryLedgerError`.

## S148-005 | PASS | Tests exercise real behavior

The added tests use the real isolated runtime and `InventoryLedgerRepository` / module-level functions. They insert actual encrypted secure-object rows, trigger duplicate ledger and duplicate movement refusals, and assert the typed localized error metadata.

Validation:

- `uv run --no-sync pytest -q src/aeat/adapters/persistence/profile/test_inventory.py src/aeat/adapters/persistence/profile/test_inventory_roundtrip.py src/aeat/application/inventory/test_inventory.py src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py -k "inventory"` passed with 30 selected tests.
- `uv run --no-sync ruff check src/aeat/adapters/persistence/profile/inventory.py src/aeat/adapters/persistence/profile/test_inventory.py src/aeat/adapters/persistence/profile/test_inventory_roundtrip.py` passed.
- `uv run --no-sync -q python -m aeat.locales audit` passed after locale updates through `python -m aeat.locales scaffold` and sequential `python -m aeat.locales set`.
- The touched-file source scan found no direct settings construction, environment access, print/typer output, suppressing pragmas, fake/stub/monkeypatch markers, skipped/xfail tests, broad exception catches, raw UTF-8 literals, or local `Path("db://secure_objects")` construction.

Disposition: close `AFR-046` as `runtime-default`.
