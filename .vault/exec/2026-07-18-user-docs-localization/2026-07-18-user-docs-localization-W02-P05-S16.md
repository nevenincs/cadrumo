---
tags:
  - '#exec'
  - '#user-docs-localization'
date: '2026-07-18'
modified: '2026-07-18'
step_id: 'S16'
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
     The S16 and 2026-07-18-user-docs-localization-plan placeholders are machine-filled by
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
     The Translate the how-to section catalogues to Hungarian with full-page domain context and ## Scope

- `docs/locales/hu` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Translate the how-to section catalogues to Hungarian with full-page domain context

## Scope

- `docs/locales/hu`

## Description

- Translate the how-to section catalogues to Hungarian with full-page domain context, worked across batched commits.
- Spanish-stem AEAT nouns kept invariant in the Hungarian prose.

## Outcome

The `docs/locales/hu/LC_MESSAGES/how-to/**` catalogues are fully translated. Delivered across 11 commits tagged `W02.P05.S16` (representative: e4d40357da, 19f033fb90, 1ec9c7411b). Rolled into the hu language reaching 2994/2994 entries, zero untranslated, zero fuzzy at HEAD.

## Notes

Evidence reconstructed from `git log --oneline --grep "W02.P05.S16"` after delivery. Vault-only closure.
