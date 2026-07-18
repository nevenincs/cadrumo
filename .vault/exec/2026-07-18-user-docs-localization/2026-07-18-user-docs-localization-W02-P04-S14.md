---
tags:
  - '#exec'
  - '#user-docs-localization'
date: '2026-07-18'
modified: '2026-07-18'
step_id: 'S14'
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
     The S14 and 2026-07-18-user-docs-localization-plan placeholders are machine-filled by
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
     The Translate the explanation and reference section catalogues to Catalan and ## Scope

- `docs/locales/ca` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Translate the explanation and reference section catalogues to Catalan

## Scope

- `docs/locales/ca`

## Description

- Translate the explanation and reference section catalogues to Catalan (7 pages each section).

## Outcome

The `docs/locales/ca/LC_MESSAGES/explanation/**` and `.../reference/**` catalogues are fully translated. Delivered across commits tagged `W02.P04.S14` (9eaacfb018, 1ab50bb725, 67863b4a1c). Rolled into the ca language reaching 2994/2994 entries, zero untranslated, zero fuzzy at HEAD.

## Notes

The ca reference/review-calculation-values catalogue carried a pre-existing non-breaking-space drift on one maritime-exemption msgid, surfaced and reconciled (fuzzy cleared, translation correct) in the W03 pass (commit 167961772c); ca stayed 100% complete. Vault-only closure.
