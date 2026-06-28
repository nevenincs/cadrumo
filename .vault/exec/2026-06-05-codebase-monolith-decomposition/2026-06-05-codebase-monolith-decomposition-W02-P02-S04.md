---
tags: ['#exec', '#codebase-monolith-decomposition']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S04'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W02.P02.S04 - ledger business invoice extraction

Scope: `src/aeat/entrypoints/cli/_ledger.py` and `src/aeat/entrypoints/cli/_ledger_business_invoice_cli.py`.

## Description

- Added `_ledger_business_invoice_cli.py` as the focused Typer registrar for payable and collectible business invoice commands.
- Moved command transport, output projection, and service invocation for business invoice verbs out of `_ledger.py`.
- Replaced the removed `_ledger.py` command block with `register_business_invoice_commands(app)`.
- Preserved `_ledger.py` as the top-level export facade for `payable_invoice_app` and `collectible_invoice_app`.

## Outcome

`_ledger.py` no longer owns the business invoice command bodies. The new module consumes `PayableInvoiceService`, `CollectibleInvoiceService`, `BusinessOperationInvoicePatch`, `IntracomOperationType`, and `validate_eu_iva_id` through the application ledger facade.

The extraction removed the selected command block from the ledger root while keeping existing test imports stable through explicit `__all__` facade exports.

## Notes

The CLI still performs transport-level parsing of decimals and operation-type strings before calling the application service. Deeper removal of policy-like parsing from CLI should be handled by a later ADR-backed backend interface change if the application facade needs a string-command DTO.
