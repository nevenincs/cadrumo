---
tags:
  - '#exec'
  - '#binding-vocabulary-cli-cohesion'
date: '2026-06-26'
modified: '2026-07-17'
body_hash: 'sha256:74a1d43b9ee51fccb3b7d3899c3ff019e0490516c4b604a66ce57ae39840486a'
step_id: 'S09'
related:
  - "[[2026-06-26-binding-vocabulary-cli-cohesion-plan]]"
---

# Rename the BusinessOperationInvoiceSourceKind TYPE to BusinessOperationInvoiceDirection (invoice-direction axis) KEEPING the payable_invoice / collectible_invoice member STRING values load-bearing per aeat-spanish-stem-naming, as one atomic relocation:BusinessOperationInvoiceSourceKind commit, sweeping all 31 occurrences across the ledger invoice CLI, the invoices _source_resolver, _business_operation_invoice.py, the ledger __init__ re-export, and the two test modules

## Scope

- `regen docs-scaffold + locale + API-stub + docstring-core-struct in the same commit`
- `collect-only clean before commit`
- `apply-cached own-only`
- `abort-on-WIP`
- `src/aeat/application/ledger/_business_operation_invoice.py`
- `src/aeat/application/ledger/__init__.py`
- `src/aeat/entrypoints/cli/_ledger_business_invoice_cli.py`
- `src/aeat/application/invoices/_source_resolver.py`

## Description

- Rename the invoice-direction enum TYPE from the `SourceKind` homonym to `BusinessOperationInvoiceDirection` (the payable-vs-collectible direction axis).
- Preserve the member string values `payable_invoice` and `collectible_invoice` (the load-bearing internal source-kind taxonomy per the Spanish-stem-naming rule); only the type name moves.
- Sweep all 31 occurrences across the ledger invoice CLI, the invoices source-resolver, `_business_operation_invoice` (def, field/param annotations, constructor assignments, `__all__`), the ledger `__init__` re-export, and the two test modules; leave the `invoice_direction_to_source_kind` function name and the `source_kind` record field name untouched.

## Outcome

Landed as one atomic commit `relocation:BusinessOperationInvoiceSourceKind` (`c39039700`). The axis is NOT folded into `BindingSourceKind`. collect-only clean, ruff clean (three import/`__all__` repositionings to the alphabetical slot, each verified as the single own rename move), the 47 ledger-invoice and source-resolver tests green, and the member strings verified unchanged in the staged diff.

## Notes

All six scoped files were clean of peer WIP, so a direct explicit-path stage and verified-index commit were sufficient. The enum docstring was clarified to state the member strings are the load-bearing source-kind taxonomy and only the type name is the direction axis.
