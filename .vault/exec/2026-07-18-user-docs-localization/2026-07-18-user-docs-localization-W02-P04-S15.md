---
tags:
  - '#exec'
  - '#user-docs-localization'
date: '2026-07-18'
modified: '2026-07-18'
step_id: 'S15'
related:
  - "[[2026-07-18-user-docs-localization-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace user-docs-localization with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S15 and 2026-07-18-user-docs-localization-plan placeholders are machine-filled by
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
     The Translate the index, architecture, top-level, and remaining catalogues to Catalan and drive the Catalan completeness gate green and ## Scope

- `docs/locales/ca` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Translate the index, architecture, top-level, and remaining catalogues to Catalan and drive the Catalan completeness gate green

## Scope

- `docs/locales/ca`

## Description

- Translate the index, architecture, top-level, and remaining catalogues to Catalan.
- Drive the Catalan completeness gate green.

## Outcome

Catalan is complete: 2994/2994 entries translated, zero untranslated, zero fuzzy across all 57 page catalogues. The Catalan completeness gate passes. Delivered under commit d9eb952e30 tagged `W02.P04.S15` (top-level pages, 8 pages), closing the Catalan phase.

## Notes

Vault-only closure; evidence from `git log --oneline --grep "W02.P04.S15"`.
