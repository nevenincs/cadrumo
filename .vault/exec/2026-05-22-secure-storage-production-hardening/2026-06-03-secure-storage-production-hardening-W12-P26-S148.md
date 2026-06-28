---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
modified: '2026-06-03'
step_id: 'S148'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-03-secure-storage-production-hardening-w12-p26-s148-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S148`

Closed `AFR-046` for profile inventory ledger persistence.

## Description

- Reviewed `src/aeat/adapters/persistence/profile/inventory.py` against the `secure-object`, `sql-route`, and `plain-file` scanner signals.
- Rejected the prior `retired` target because the inventory application service and runtime migration tests actively import and exercise `InventoryLedgerRepository`.
- Corrected the plan target for `AFR-046` and `W12.P26.S148` to `runtime-default`.
- Kept the repository enrolled in the registered FINANCIAL secure-object namespace `profile_inventory_ledger`.
- Routed logical marker paths through the centralized `secure_object_logical_path()` helper instead of local `db://secure_objects` construction.
- Replaced raw UTF-8 literals in the repository and inventory corruption test with `UTF_8_ENCODING`.
- Added localized `InventoryLedgerError` messages and structured contexts for load failure, duplicate ledger, duplicate movement, and missing ledger refusals.
- Added sanitized debug logging before wrapping secure-object load failures.
- Added real isolated-runtime tests for duplicate ledger and duplicate movement localized refusals.
- Closed `W12.P26.S148` through `vaultspec-core vault plan step check` and aligned the AFR register row to `closed`.

## Outcome

`AFR-046` is closed as `runtime-default`, not `retired`.

Validation passed:

- `uv run --no-sync pytest -q src/aeat/adapters/persistence/profile/test_inventory.py src/aeat/adapters/persistence/profile/test_inventory_roundtrip.py src/aeat/application/inventory/test_inventory.py src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py -k "inventory"`
- `uv run --no-sync ruff check src/aeat/adapters/persistence/profile/inventory.py src/aeat/adapters/persistence/profile/test_inventory.py src/aeat/adapters/persistence/profile/test_inventory_roundtrip.py`
- `uv run --no-sync -q python -m aeat.locales audit`
- `rg -n 'Settings\(|os\.environ|print\(|typer\.echo|# noqa|pragma|type: ignore|monkeypatch|_Fake|_Stub|skip\(|xfail|except Exception|except BaseException|contextlib\.suppress|"utf-8"|Path\("db://secure_objects"\)' src/aeat/adapters/persistence/profile/inventory.py src/aeat/adapters/persistence/profile/test_inventory.py src/aeat/adapters/persistence/profile/test_inventory_roundtrip.py`

## Notes

The step surfaced a plan classification defect: the inventory adapter is not deprecated or dead code. Removing it would break the current application inventory service and migrated repository tests.
