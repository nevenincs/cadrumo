---
tags:
  - '#exec'
  - '#m303-refund-fichero-block'
date: '2026-07-04'
modified: '2026-07-04'
step_id: 'S09'
related:
  - "[[2026-06-24-m303-refund-fichero-block-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace m303-refund-fichero-block with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S09 and 2026-06-24-m303-refund-fichero-block-plan placeholders are machine-filled by
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
     The Add the disposition-keyed conditional DID-page emission guard so a non-refund filing emits no empty DID page and ## Scope

- `src/aeat/application/filing/_export.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Add the disposition-keyed conditional DID-page emission guard so a non-refund filing emits no empty DID page

## Scope

- `src/aeat/application/filing/_export.py`

## Description

- Add the disposition-keyed conditional emission guard for the cuenta-devolucion (DID) page in the filing export layer so a non-refund filing emits no empty DID record.
- Suppress the `page_did` record type when the disposition is not a refund, since a non-refund filing has no refund account to declare and an emitted DID page would write an empty fixed-width record the Diseno reserves for refunds.

## Outcome

- The `_did_page_suppressed` predicate and the `_DID_PAGE_RECORD_TYPE = "page_did"` constant live in `src/aeat/application/filing/_export.py`, gating DID-page emission on the refund disposition.
- The non-refund golden-SHA M303 case asserts the DID open tag and DID page identifier are absent and the fichero shrinks accordingly; the refund case asserts the DID page is present. Both pass at HEAD.

## Notes

- This record documents the verified landed state at HEAD; suppression mirrors the official DR303 structure, which emits the DID page only for a devolucion.
