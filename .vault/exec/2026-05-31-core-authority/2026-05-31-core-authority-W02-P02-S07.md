---
tags:
  - '#exec'
  - '#core-authority'
step_id: S07
date: '2026-05-31'
modified: '2026-05-31'
related:
  - '[[2026-05-31-core-authority-plan]]'
  - '[[2026-05-31-core-authority-adr]]'
---

# core-authority W02.P02.S07 — Domain ER-02 ValidationError family -> CoreValidationError

## Deviation from plan

Plan prescribed `src/aeat/adapters/_errors.py` which does not exist. Actual
target per PAIR ER-02 (semantic-v2-reference): three domain ValidationError
classes not yet migrated.

## Changes

- `RegistryValidationError(RegistryError)` → `(RegistryError, CoreValidationError)`
- `InvoiceValidationError(InvoiceError, ValueError)` → `(InvoiceError, CoreValidationError)`
- `InventoryValidationError(InventoryLedgerError, ValueError)` → `(InventoryLedgerError, CoreValidationError)`

All MROs verified via Python interpreter — correct C3 linearisation confirmed.

## Verification gate

`pytest src/aeat/domain/invoices/ src/aeat/domain/profile/ -q` — 300 passed.
Registry: 60 passed (1 pre-existing catalogue coverage failure unrelated).

## Commit

`5418c1333` — feat(errors): W02.P02.S07 ER-02 domain ValidationError family -> CoreValidationError
