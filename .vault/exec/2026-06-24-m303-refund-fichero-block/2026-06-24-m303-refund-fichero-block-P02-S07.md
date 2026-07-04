---
tags:
  - '#exec'
  - '#m303-refund-fichero-block'
date: '2026-07-04'
modified: '2026-07-04'
step_id: 'S07'
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
     The S07 and 2026-06-24-m303-refund-fichero-block-plan placeholders are machine-filled by
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
     The Read the refund-account block from secure storage transiently and emit the IBAN, SWIFT-BIC, sepa_marca, and per-marca bank sub-fields only on a refund disposition and ## Scope

- `src/aeat/application/modelo/_export.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Read the refund-account block from secure storage transiently and emit the IBAN, SWIFT-BIC, sepa_marca, and per-marca bank sub-fields only on a refund disposition

## Scope

- `src/aeat/application/modelo/_export.py`

## Description

- Read the refund-account block from encrypted secure storage transiently at export and populate the DR303 cuenta-devolucion (DID) page only on a refund disposition.
- Emit the IBAN at DID offset 23, the SWIFT-BIC at DID offset 12, the derived Marca SEPA at DID offset 194, and the per-marca foreign-bank sub-fields (name, address, city, country) for a non-SEPA (Resto Paises) account.
- Build the `RefundAccount` carrier from the profile facts and hand it to the header composer so the account data never reaches a log or plaintext side store.

## Outcome

- The M303 export path in `src/aeat/application/modelo/_export.py` imports `RefundAccount` and `derive_sepa_marca`, reads the account transiently, and emits the DID sub-fields keyed by the determined disposition.
- `test_export_refund_did.py` and the refund golden-SHA M303 cases assert the SEPA case emits IBAN-only DID fields and the non-SEPA case emits the full foreign-bank block, all at the DR303-prescribed offsets. Both pass at HEAD.

## Notes

- This record documents the verified landed state at HEAD; the refund-account bytes are held only transiently in memory during export, honouring the secure-storage-only mandate.
