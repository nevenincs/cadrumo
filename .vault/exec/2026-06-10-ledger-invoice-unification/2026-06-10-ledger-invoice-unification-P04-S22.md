---
tags:
  - '#exec'
  - '#ledger-invoice-unification'
date: '2026-06-11'
step_id: 'S22'
related:
  - '[[2026-06-10-ledger-invoice-unification-plan]]'
---

# Enum Inventory Gate Update

## Scope

C4 ledger invoice unification reconciliation for `P04.S22`.

## Description

- Rewrote the bare invoice source-kind inventory assertion so production code must not revive the retired alias.
- Updated the failure guidance to point to `payable_invoice`, `collectible_invoice`, or `purchase_invoice_evidence`.

## Outcome

The inventory gate now enforces deletion of the bare invoice source-kind alias instead of requiring enum indirection for it.

## Verification

- `uv run --no-sync pytest -m "integration or not integration" src/aeat/tests/test_enum_constant_extraction_inventory.py -q` was included in the 203-test focused green gate.
- Production-only bare-source search returned no matches.
