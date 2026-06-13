---
tags:
  - '#exec'
  - '#m303-form-vs-semantic-casilla-dual-keying'
date: '2026-06-13'
step_id: 'S21'
related:
  - "[[2026-06-13-m303-form-vs-semantic-casilla-dual-keying-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace m303-form-vs-semantic-casilla-dual-keying with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.
     step_id is the originating Step's canonical identifier, e.g. S01.

     Related: use wiki-links as '[[YYYY-MM-DD-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add frontmatter fields
     outside the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path. -->

# Verify the BOE/fichero export field modelo-303-page-01-casilla-27 and the sibling casilla-NN export refs now write the projected value not zero, and confirm the workbook/BOE parity gate stays green (modelo-export-mirrors-official-structure)

## Scope

- `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/export/`

## Description

- Verify export-ref value carriage: the casilla-27 export field still targets box 27, which now carries the projected (non-zero) cuota on a ledger-fed calculate, so the export reads value not zero.
- test_export_ref_points_at_projected_box_carrying_value asserts this; the existing fichero export test (test_export_modelo_303_wallet_only...) exercises the full BOE render with non-zero repercutido. The workbook/BOE parity gate (test_record_design completeness manifest, test_registry_reviewability) stays green after adding the ten boxes to the manifest fragment.

## Outcome

- Step landed; focused gates green (registry M303 load, verification-substance operator parity, the M303 official-box projection suite).

## Notes

- The DSL-operator edits touch `_schema.py` and `_verification_actions.py`, which carried concurrent peer WIP (a DT-12 advisory extraction). The edits are additive and in disjoint regions; the working tree is internally consistent and all focused tests pass.
