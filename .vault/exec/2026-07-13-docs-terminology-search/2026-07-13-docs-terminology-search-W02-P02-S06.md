---
tags:
  - '#exec'
  - '#docs-terminology-search'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S06'
related:
  - "[[2026-07-13-docs-terminology-search-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace docs-terminology-search with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S06 and 2026-07-13-docs-terminology-search-plan placeholders are machine-filled by
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
     The Prove per-kind parity: preprocess run-one output text equals the committed sidecar text for a representative source of each kind, asserted by a committed test and ## Scope

- `dev/docs/preprocess/tests/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Prove per-kind parity: preprocess run-one output text equals the committed sidecar text for a representative source of each kind, asserted by a committed test

## Scope

- `dev/docs/preprocess/tests/`

## Description

- Add `test_hook_units_are_parity_with_committed_sidecars`, parametrised per
  source kind, asserting hook unit texts equal committed sidecar unit texts
  for the smallest representative of each kind.
- Run the real upstream runner end to end per kind.

## Outcome

7/7 hook gates green (`485ac85614`). Live `preprocess run-one` evidence:
HTML representative preprocessed with 2 sections, PDF (calendario
contribuyente 2025) with 82, Diseños workbook (modelo 036) with 13.

## Notes

The atomic cutover (S07) stays open: resolver retarget, sidecar deletion,
docstring correction, and the equal-or-superset sweep proof land together.
