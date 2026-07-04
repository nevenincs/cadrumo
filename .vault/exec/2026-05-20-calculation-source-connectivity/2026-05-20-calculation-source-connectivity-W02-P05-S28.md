---
tags:
  - '#exec'
  - '#calculation-source-connectivity'
date: '2026-07-04'
modified: '2026-07-04'
step_id: 'S28'
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
     The S28 and 2026-05-20-calculation-source-connectivity-plan placeholders are machine-filled by
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
     The Adapt collectible invoice records into source mesh resolution and ## Scope

- `src/aeat/application/ledger/_business_operation_invoice.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Adapt collectible invoice records into source mesh resolution

## Scope

- `src/aeat/application/ledger/_business_operation_invoice.py`

## Description

Verified the step is already implemented at HEAD by prior source-mesh work; this record closes it against real gate evidence rather than re-implementing.

- Confirmed slim collectible `BusinessOperationInvoice` records are adapted into source-mesh resolution by `InvoiceCatalogueSourceResolver`, which loads them through `BusinessOperationInvoiceRepository`, filters by bucket and filing period, and normalises them into registry `InvoiceObservation` facts.
- Confirmed the `collectible_invoice` binding source kind is `ENROLLED`: the resolver owns it and is wired into the live `merge_source_resolutions` mesh tuple, so a collectible-invoice binding cannot resolve to a silent blank; Modelo 349 declares `collectible_invoice`.
- Confirmed collectible observations carry stable provenance (source kind, `collectible_invoice:<invoice_id>` source ref, SHA-256 fingerprint) and drive the Modelo 349 operador detail rows and declarante summary bindings.

## Outcome

Collectible invoice records are adapted into source-mesh resolution and the `collectible_invoice` source kind is enrolled on the live mesh. No production code change was required; the step was already satisfied at HEAD by the same resolver that closed S25.

Gate evidence: `test_source_resolver.py` green (collectible observation, source ref, fingerprint, transaction ids); the reflective enrollment gate `test_source_resolver_enrollment.py` green; the source-mesh contract test `test_source_mesh.py` green.

## Notes

Closed as verified-at-HEAD. The plan named `src/aeat/application/ledger/_business_operation_invoice.py` as the adaptation site; the realized adaptation reads those records through `BusinessOperationInvoiceRepository` and converges them in `InvoiceCatalogueSourceResolver` (`src/aeat/application/invoices/_source_resolver.py`). The `invoice_direction_to_source_kind` mapping owns the issued to collectible, received to payable correspondence.
