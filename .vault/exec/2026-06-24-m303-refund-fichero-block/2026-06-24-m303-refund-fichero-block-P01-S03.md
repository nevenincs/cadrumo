---
tags:
  - '#exec'
  - '#m303-refund-fichero-block'
date: '2026-07-04'
modified: '2026-07-04'
step_id: 'S03'
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
     The S03 and 2026-06-24-m303-refund-fichero-block-plan placeholders are machine-filled by
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
     The Add export_headers redeme to the redeme_enrolled schema field for the page-1 indicator and ## Scope

- `src/aeat/_data/registry/aeat/user_profile/schema.toml` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Add export_headers redeme to the redeme_enrolled schema field for the page-1 indicator

## Scope

- `src/aeat/_data/registry/aeat/user_profile/schema.toml`

## Description

- Add the `redeme` export-header alias to the `redeme_enrolled` boolean field's `export_headers` list on the central schema so the fichero page-1 REDEME indicator can resolve from the standing profile fact.
- Keep the field `sensitivity = "financial"` and grounded in `rd-1624-1992:art-30`, with its model selector and schedule predicate wiring intact.

## Outcome

- The `redeme_enrolled` field carries `export_headers = ["redeme"]` in `src/aeat/_data/registry/aeat/user_profile/schema.toml` at HEAD.
- The M303 header composer resolves the `redeme` header to the REDEME byte at DR303 page-1 offset 110, verified by the golden-SHA fichero tests which assert the byte value at offset 110 for both a REDEME and a non-REDEME filer.

## Notes

- This record documents the verified landed state at HEAD.
