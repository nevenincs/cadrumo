---
tags:
  - '#exec'
  - '#m303-refund-fichero-block'
date: '2026-07-04'
modified: '2026-07-04'
step_id: 'S06'
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
     The S06 and 2026-06-24-m303-refund-fichero-block-plan placeholders are machine-filled by
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
     The Add the sepa_marca derivation (1 Espana / 2 UE SEPA / 3 Resto) from the refund-account country and ## Scope

- `src/aeat/domain/iva/_refund_eligibility.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Add the sepa_marca derivation (1 Espana / 2 UE SEPA / 3 Resto) from the refund-account country

## Scope

- `src/aeat/domain/iva/_refund_eligibility.py`

## Description

- Add the `derive_sepa_marca` function and the `SepaMarca` closed enum classifying the refund account for the DR303 Marca SEPA indicator at DID position 194: `"1"` Cuenta Espana, `"2"` UE SEPA, `"3"` Resto Paises.
- Derive the marca from the account country (the IBAN country code prefix, or the explicit bank country code for a non-SEPA account) and that country's membership of the SEPA zone, rather than storing it as an operator input.
- Ground the SEPA-zone country set in the European Payments Council EPC List of SEPA Scheme Countries (EPC409-09) and Regulation (EU) No 260/2012.

## Outcome

- `derive_sepa_marca` and `SepaMarca` live in `src/aeat/domain/iva/_sepa_marca.py`, exported from the iva package facade, and consumed by the M303 export path.
- The refund golden-SHA cases assert the derived Marca SEPA byte at DID offset 194 is `"1"` for an ES IBAN and the non-SEPA case emits `"3"` with the foreign-bank block. Both pass at HEAD.

## Notes

- The plan Step named `src/aeat/domain/iva/_refund_eligibility.py` as the scope; the implementation instead placed the derivation in a dedicated `_sepa_marca.py` module, a clearer single-responsibility home. This is a scope-file naming deviation only; the functional intent (derive the Marca SEPA from the account country) is satisfied.
- This record documents the verified landed state at HEAD.
