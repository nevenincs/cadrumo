---
tags:
  - '#exec'
  - '#calculation-source-connectivity'
date: '2026-07-04'
modified: '2026-07-17'
body_hash: 'sha256:2097ef6e2fc4ce4640720cd54bb8cd1ab3115b15dc6d0b46943a60ae6324f375'
step_id: 'S31'
related:
  - "[[2026-05-20-calculation-source-connectivity-plan]]"
---

# Test invoice ledger cross references produce stable source refs

## Scope

- `src/aeat/application/aggregation/test_source_mesh_invoices.py`

## Description

Verified the required test coverage exists at HEAD; this record closes the test step against the realized coverage rather than adding a duplicate file.

- Confirmed `test_source_resolver.py` asserts that invoice records cross-referenced to ledger transactions produce stable source refs: the resolution's `source_transaction_ids` equal the invoice `linked_transaction_ids`, and each provenance row carries a deterministic `<source_kind>:<invoice_id>` source ref plus a `sha256:`-prefixed fingerprint.
- Confirmed the coverage spans both invoice source kinds and both record shapes: the governed `InvoiceCatalogue` invoices and the slim ledger-mounted `BusinessOperationInvoice` payable and collectible records converge on the same provenance contract.
- Confirmed the fingerprint is derived from the canonical observation JSON, so the source ref is stable across resolutions of unchanged invoice data and changes when the observed facts change (the basis for approval staleness).

## Outcome

Invoice ledger cross-references are proven to produce stable source refs by the consolidated invoice source-resolver test. No new test file was required; the plan's `test_source_mesh_invoices.py` intent is satisfied by `test_source_resolver.py`.

Gate evidence: `test_source_resolver.py` green (source ref, fingerprint, transaction-id stability for payable and collectible, catalogue and business-operation records).

## Notes

Closed as verified-at-HEAD. The plan named a standalone `test_source_mesh_invoices.py`; the realized coverage lives in `src/aeat/application/invoices/tests/test_source_resolver.py`, co-located with the resolver it exercises per the tests-live-under-domain-tests-folders topology.
