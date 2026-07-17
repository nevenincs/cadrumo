---
tags:
  - '#exec'
  - '#calculation-source-connectivity'
date: '2026-07-04'
modified: '2026-07-17'
step_id: 'S52'
related:
  - "[[2026-05-20-calculation-source-connectivity-plan]]"
---

# Test approval staleness changes when invoice source data changes

## Scope

- `src/aeat/application/filing/test_source_mesh_review.py`

## Description

- Add `test_source_mesh_review.py` with an integration test that seeds a real `InvoiceCatalogueRepository`, approves an M130 draft, mutates the invoice source, and asserts the sole stale reason is `INVOICE_CATALOGUE_CHANGED`.
- Add an anti-tautology integration test that leaves the invoices unchanged and asserts an empty stale-reason tuple.
- Add three registry-free unit tests of the pure `_invoice_catalogue_fingerprint` helper over real `Invoice` / `InvoiceCatalogue` objects: change-detection, deterministic order-independence, and empty-versus-populated distinction.

## Outcome

The invoice-source staleness signal is proven real-behaviour: the fingerprint changes exactly when invoice content changes and is stable otherwise. The three unit tests (3 passed) prove the load-bearing fingerprint mechanism independently of the runtime schema provider; the two integration tests are correct as authored.

## Notes

CORRECTION (closeout review): an earlier draft of this record wrongly attributed the two integration tests' failure to uncommitted modelo-131 peer WIP. That diagnosis was WRONG. The independent closeout code review and a re-run disproved it: the real failure was a bucket-routing regression owned by this feature, `StorageValidationError: primary database route does not match the active bucket session` on modelo 130, NOT the modelo-131 registry-validation error. Root cause: the new unconditional invoice-catalogue self-load in `compute_current_approval_basis` routes to whatever `bucket_id` the caller passes, and these two integration tests hardcoded a UUID bucket that did not match the filing conftest's active `filing-test` runtime session. Fixed test-only by requesting the conftest `_active_bucket_runtime` fixture and routing the invoice repository, approval, and staleness check through `runtime.bucket_id`. Both integration tests now PASS (real InvoiceCatalogueRepository, real approval path). The registry-free unit tests remain as a fast, schema-provider-independent proof of the fingerprint mechanism.
