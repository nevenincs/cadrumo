---
tags:
  - '#exec'
  - '#calculation-source-connectivity'
date: '2026-07-04'
modified: '2026-07-17'
step_id: 'S49'
related:
  - "[[2026-05-20-calculation-source-connectivity-plan]]"
---

# Include resolver fingerprints in approval basis

## Scope

- `src/aeat/application/filing/_review.py`

## Description

- Add `invoice_catalogue_fingerprint` to `ModeloApprovalBasis` and bump `APPROVAL_BASIS_VERSION` from `review-basis-v1` to `review-basis-v2` with no migration or read-tolerance shim.
- Add the `INVOICE_CATALOGUE_CHANGED` stale reason and its four-locale translation via the locale CLI.
- Self-load the bucket invoice catalogue in `compute_current_approval_basis` (mirroring the transaction-catalogue self-load) and fingerprint it order-independently over the frozen invoice records.
- Compare the new fingerprint in `approval_stale_reasons`; thread an optional `invoice_catalogue` override through `approve_draft` and `refresh_review_status`.
- Update the two direct `ModeloApprovalBasis` construction sites in the domain-filing roundtrip tests to carry the new required field.

## Outcome

An `APROBADO` draft now goes stale when the bucket's upstream issued/received invoices change, closing the gap where only the ledger transaction catalogue was fingerprinted. Stale detection is reproducible at refresh time (the fingerprint self-loads from `bucket_id`) with no source-mesh dependency in the review layer.

## Notes

Scope deliberately narrowed to the invoice catalogue. A full multi-resolver mesh fingerprint (profile, previous_filing, relations) is NOT reproducibly self-loadable from `bucket_id` alone in the review layer — it needs the `ModeloRevision` plus prior-work-unit context, i.e. running the whole mesh inside the review layer, a heavy cross-layer coupling the boundary forbids. That fuller fingerprint is deferred to a tracked follow-up plan row. The v1-to-v2 bump correctly trips `APPROVAL_BASIS_VERSION_CHANGED` on any pre-upgrade stored basis (re-approve after upgrade); acceptable in this unreleased pre-beta project per the no-legacy rule.

CORRECTION (closeout review): the unconditional invoice self-load added here regressed the filing tests that approve a draft against a non-active/sentinel bucket without an `invoice_catalogue` override (the established contract already required a `transaction_catalogue` override for the same reason). The production logic was found CLEAN and unchanged; the fix was test-only — every approval site that overrides `transaction_catalogue` now also overrides `invoice_catalogue`, applied at the shared `build_registry_filing_draft` helper plus the four `test_filing.py` fingerprint tests. An earlier record wrongly blamed modelo-131 peer WIP; that attribution was a misdiagnosis (see S52/S54 records). Full `application/filing/tests` suite green (267 passed).
