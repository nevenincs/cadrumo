---
tags:
  - '#exec'
  - '#calculation-source-connectivity'
date: '2026-07-04'
modified: '2026-07-17'
body_hash: 'sha256:669688e2bda0a567503f7f3801b5effe8a0cc9b1cb5d69e994f8e01a06b6410e'
step_id: 'S27'
related:
  - "[[2026-05-20-calculation-source-connectivity-plan]]"
---

# Adapt payable invoice records into source mesh resolution

## Scope

- `src/aeat/application/ledger/_business_operation_invoice.py`

## Description

Verified the step is already implemented at HEAD by prior source-mesh work; this record closes it against real gate evidence rather than re-implementing.

- Confirmed slim payable `BusinessOperationInvoice` records are adapted into source-mesh resolution by `InvoiceCatalogueSourceResolver`, which loads them through `BusinessOperationInvoiceRepository`, filters by bucket and filing period, and normalises them into registry `InvoiceObservation` facts.
- Confirmed the `payable_invoice` binding source kind is `ENROLLED`: the resolver owns it and is wired into the live `merge_source_resolutions` mesh tuple on the calculate path, so a payable-invoice binding cannot resolve to a silent blank.
- Confirmed payable observations carry stable provenance (source kind, `payable_invoice:<invoice_id>` source ref, SHA-256 fingerprint) and feed the Modelo 349 declarante summary and operador detail rows.

## Outcome

Payable invoice records are adapted into source-mesh resolution and the `payable_invoice` source kind is enrolled on the live mesh. No production code change was required; the step was already satisfied at HEAD by the same resolver that closed S25.

Gate evidence: `test_source_resolver.py` green (payable observation, source ref, fingerprint, transaction ids); the reflective enrollment gate `test_source_resolver_enrollment.py` green; the source-mesh contract test `test_source_mesh.py` green.

## Notes

Closed as verified-at-HEAD. The plan named `src/aeat/application/ledger/_business_operation_invoice.py` as the adaptation site; the realized adaptation reads those records through `BusinessOperationInvoiceRepository` and converges them in `InvoiceCatalogueSourceResolver` (`src/aeat/application/invoices/_source_resolver.py`).
