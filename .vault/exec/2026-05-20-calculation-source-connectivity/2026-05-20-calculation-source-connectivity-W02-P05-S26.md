---
tags:
  - '#exec'
  - '#calculation-source-connectivity'
date: '2026-07-04'
modified: '2026-07-17'
step_id: 'S26'
related:
  - "[[2026-05-20-calculation-source-connectivity-plan]]"
---

# Adapt purchase invoice evidence records into source mesh resolution

## Scope

- `src/aeat/application/ledger/_evidence.py`

## Description

Verified the step is already implemented at HEAD by prior source-mesh work; this record closes it against real gate evidence rather than re-implementing.

- Confirmed `PurchaseInvoiceEvidence` records are adapted into typed source observations consumed on the live calculate path through `LedgerRentaExpenseAggregationSourceResolver`, which takes the invoice repository and links purchase-invoice evidence to outgoing transactions by `purchase_invoice_evidence_id`.
- Confirmed the resolver emits typed diagnostics for every evidence pathology rather than a silent blank: missing evidence, unsupported evidence kind, bucket mismatch, link mismatch, and partial/multi-transaction evidence.
- Confirmed the standalone `purchase_invoice_evidence` binding source kind carries no committed registry binding and is therefore classified `RESERVED` in the disposition registry (invoice-shaped headroom), so no dormant standalone resolver is built for it, honouring the no-dormant-source-resolvers rule.

## Outcome

Purchase invoice evidence is adapted into source resolution as an evidence input to the Renta expense aggregation resolver, with the standalone source kind held as `RESERVED` headroom. No production code change was required; the step was already satisfied at HEAD.

Gate evidence: `test_renta_ledger.py` green (purchase-invoice evidence linking, bucket-mismatch rejection, unbound-repository rejection, period filtering); the source-mesh disposition governance gate `test_source_kind_enrollment_status.py` green.

## Notes

Closed as verified-at-HEAD. The plan named `src/aeat/application/ledger/_evidence.py` as the adaptation site; the realized adaptation flows through the Renta expense resolver in `src/aeat/application/aggregation/_renta_ledger.py`, which consumes the `_evidence.py` records. The standalone `purchase_invoice_evidence` source kind remains `RESERVED` pending a modelo that declares it as a first-class binding source.
