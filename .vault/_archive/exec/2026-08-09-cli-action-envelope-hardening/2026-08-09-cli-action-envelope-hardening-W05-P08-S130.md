---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:cd2f5db09cdd74ea8211707bf325e31cf980bdb90bb46b67b00b458ac19751ac'
step_id: 'S130'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---
# Publish invoice and IVA validation ownership and unify ledger terminal projection

## Scope

- `src/cadrumo/domain/invoices/_models.py`
- `src/cadrumo/domain/iva/_classification.py`
- `src/cadrumo/entrypoints/cli/_ledger_support.py`
- `src/cadrumo/entrypoints/cli/_ledger*.py`
- `src/cadrumo/entrypoints/cli/tests`
- `dev/tests/test_invoice_iva_validation_owner_census.py`

## Description

- Ratchet 36 physical invoice raise sites into 34 semantic families and classify both IVA validators by terminal owner.
- Record ledger-terminal, bulk-row, persistence-integrity, assembly-gap, and internal-unreachable dispositions.
- Route five ledger boundaries through one canonical projection for direct and purely nested invoice-domain Pydantic validation.
- Preserve mixed/non-invoice Pydantic errors and InvoiceCatalogue corruption on their existing owners.
- Add exact owner census and direct, nested, mixed, ordinary, and real JSON CLI proofs.

## Outcome

All 34 invoice families and two IVA validators have an exact durable owner/disposition. Add, wizard, import, update, and evidence-confirm delegate to one ledger support projection for `cli.ledger.invoice.valid`; direct errors and Pydantic wrappers containing only nested `InvoiceValidationError` receive the same fact-only terminal contract exactly once.

Mixed wrappers, ordinary Invoice/InvoiceLine coercion, non-invoice Pydantic errors, and InvoiceCatalogue corruption remain unprojected. The predicate requires an Invoice/InvoiceLine title, nonempty details, and every detail to preserve a nested invoice-domain error.

The final integration proof passes seven tests and the owner census passes four. Business-invoice and bulk-import consumers pass 11 and nine tests. Ruff, format, and diff checks pass; independent review found no residue.
