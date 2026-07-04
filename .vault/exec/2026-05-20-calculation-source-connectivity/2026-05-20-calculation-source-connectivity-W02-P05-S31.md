---
tags:
  - '#exec'
  - '#calculation-source-connectivity'
date: '2026-07-04'
modified: '2026-07-04'
step_id: 'S31'
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
     The S31 and 2026-05-20-calculation-source-connectivity-plan placeholders are machine-filled by
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
     The Test invoice ledger cross references produce stable source refs and ## Scope

- `src/aeat/application/aggregation/test_source_mesh_invoices.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

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
