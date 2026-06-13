---
tags: ['#exec', '#codebase-monolith-decomposition']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S10'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W02.P02.S10 - ledger inventory extraction

Scope: `src/aeat/entrypoints/cli/_ledger.py` and `src/aeat/entrypoints/cli/_ledger_inventory_cli.py`.

## Description

- Added `_ledger_inventory_cli.py` as the focused Typer registrar for inventory commands.
- Moved inventory app creation, movement and valuation child app creation, command bodies, output shaping, and service invocation out of `_ledger.py`.
- Replaced the removed `_ledger.py` command block with `register_inventory_commands(app)`.
- Preserved `_ledger.py` as the top-level export facade for `inventory_app`.

## Outcome

`_ledger.py` no longer owns the inventory command bodies. The new module consumes `InventoryService` and `InventoryMovementCommand` through the application inventory facade and keeps CLI-only decimal/date/kind parsing local to the transport module.

The ledger root now delegates both business invoice and inventory noun groups through focused registrars.

## Notes

`test_inventory_verbs.py` contained unrelated over-deep relative imports in the working tree. They blocked collection, so only that file's imports were corrected back to the package-relative form needed by the test package.
