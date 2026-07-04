---
tags:
  - '#exec'
  - '#calculation-source-connectivity'
date: '2026-07-04'
modified: '2026-07-04'
step_id: 'S52'
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
     The S52 and 2026-05-20-calculation-source-connectivity-plan placeholders are machine-filled by
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
     The Test approval staleness changes when invoice source data changes and ## Scope

- `src/aeat/application/filing/test_source_mesh_review.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

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
