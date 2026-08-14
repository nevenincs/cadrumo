---
tags:
  - '#exec'
  - '#facturae-invoice-class'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:93d4ff970401e1ff0c08b42f5d72c21f4d78eedc3b0f9810040e6bb1350fb664'
step_id: 'S02'
related:
  - "[[2026-08-13-facturae-invoice-class-plan]]"
---

# Read InvoiceClass from the Facturae header into a typed field on the parsed record, scoped to the header's own children like its siblings. An absent or unrecognised code leaves the field None and must never refuse the document

## Scope

- `src/cadrumo/adapters/inbound/einvoice/_parsers.py`

## Description

- Add the optional typed class field to the syntax-independent parsed record.
- Read `InvoiceClass` only from the Facturae header's direct children.
- Degrade absent and unknown codes to no declared class without refusing the invoice.
- Exercise the read, degradation, and descendant-scoping paths through the real parser.

## Outcome

- Facturae records now carry their recognised declared class as `FacturaeInvoiceClass`.
- Six focused adapter tests passed, including the two non-refusal cases.

## Notes

- The first focused run exposed an incorrect fixture expectation and slot ordering; both were corrected before closure.
- Verification remained adapter-scoped and does not establish repository-wide readiness.
