---
tags:
  - '#exec'
  - '#fichero-boe-parity-gate'
date: '2026-07-01'
modified: '2026-07-01'
step_id: 'S04'
related:
  - "[[2026-07-01-fichero-boe-parity-gate-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace fichero-boe-parity-gate with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S04 and 2026-07-01-fichero-boe-parity-gate-plan placeholders are machine-filled by
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
     The Widen the rendered casilla-set derivation to enumerate every casilla-bearing field kind that reaches disk and ## Scope

- `src/aeat/application/filing/_export.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Widen the rendered casilla-set derivation to enumerate every casilla-bearing field kind that reaches disk

## Scope

- `src/aeat/application/filing/_export.py`

## Description

- Add `boe_representable_casilla_ids` and `rendered_casilla_ids` to the export module, deriving the on-disk casilla set across all field kinds (xml-dictionary entries; fixed-width CASILLA fields plus binding-row `row_field_casilla_ids`) in non-suppressed records, intersected with `draft.values` for the rendered set.
- Leave `_exported_casilla_provenance` untouched; the widened enumeration is a new helper, not a mutation of the receipt provenance contract.

## Outcome

Landed with S05-S07 in the P02 commit. Ruff clean.

## Notes

Empirically grounded first: a naive manifest-subset-of-direct-CASILLA-fields check false-panics on 130 (1 casilla), 303 (19), 200 (1), and 100 (628; xml-dictionary carries zero CASILLA fields). The helper spans every casilla-bearing field kind so the gate can intersect the manifest with the truly-representable set rather than false-firing on calc-closure-only casillas.
