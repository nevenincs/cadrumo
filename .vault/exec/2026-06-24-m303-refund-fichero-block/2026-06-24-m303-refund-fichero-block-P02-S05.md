---
tags:
  - '#exec'
  - '#m303-refund-fichero-block'
date: '2026-07-04'
modified: '2026-07-04'
step_id: 'S05'
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
     The S05 and 2026-06-24-m303-refund-fichero-block-plan placeholders are machine-filled by
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
     The Emit the REDEME byte mapping redeme_enrolled to 1 or 2 in the header composer and ## Scope

- `src/aeat/application/modelo/_export.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Emit the REDEME byte mapping redeme_enrolled to 1 or 2 in the header composer

## Scope

- `src/aeat/application/modelo/_export.py`

## Description

- Emit the REDEME byte in the M303 fichero header composer at DR303 page-1 position 110, mapping the standing `redeme_enrolled` profile fact to `"1"` (SI) when enrolled and `"2"` (NO) otherwise.
- Source the byte from the workflow profile IVA facts rather than the refund disposition, so the REDEME indicator rides every M303 filing, not only refunds.

## Outcome

- The header composer in `src/aeat/application/modelo/_export.py` sets `headers["redeme"]` from `workflow_profile.iva.redeme_enrolled`.
- The golden-SHA M303 tests assert the resulting byte at page-1 offset 110 is `"1"` for a REDEME refund filer and `"2"` for a non-REDEME filer. Both pass at HEAD.

## Notes

- This record documents the verified landed state at HEAD.
