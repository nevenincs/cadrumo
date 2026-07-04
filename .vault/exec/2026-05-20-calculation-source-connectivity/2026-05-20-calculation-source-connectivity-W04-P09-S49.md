---
tags:
  - '#exec'
  - '#calculation-source-connectivity'
date: '2026-07-04'
modified: '2026-07-04'
step_id: 'S49'
related:
  - "[[2026-05-20-calculation-source-connectivity-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace calculation-source-connectivity with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S49 and 2026-05-20-calculation-source-connectivity-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Include resolver fingerprints in approval basis and ## Scope

- `src/aeat/application/filing/_review.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

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
