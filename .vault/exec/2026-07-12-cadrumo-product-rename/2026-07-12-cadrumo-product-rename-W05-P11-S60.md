---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-12'
step_id: 'S60'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cadrumo-product-rename with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S60 and 2026-07-12-cadrumo-product-rename-plan placeholders are machine-filled by
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
     The Update release-readiness project-name parsing and real behavior tests and ## Scope

- `dev/release` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Update release-readiness project-name parsing and real behavior tests

## Scope

- `dev/release`

## Description

- Parse the root and both companion project names from their real `pyproject.toml` files.
- Compare those names with the single canonical `PRODUCT_IDENTITY` distribution tuple.
- Add a blocking release-readiness result for any root or companion name drift.
- Prove every former distribution name is rejected through real temporary project files.

## Outcome

Release readiness now blocks unless the project tuple is exactly `cadrumo`,
`cadrumo-data-manuals`, and `cadrumo-data-official`. The real repository gate
reports all blocking checks clean; Ruff and all twenty-one focused tests pass.

## Notes

No compatibility alias or fallback is accepted. AEAT remains untouched where
it denotes the Spanish tax authority; this check is limited to product
distribution metadata.

The S60 plan checkbox landed concurrently with the adjacent CI-workflow step,
so the final S60 commit does not duplicate that already-closed plan byte.
