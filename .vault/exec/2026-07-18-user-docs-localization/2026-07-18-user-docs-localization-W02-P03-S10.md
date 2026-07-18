---
tags:
  - '#exec'
  - '#user-docs-localization'
date: '2026-07-18'
modified: '2026-07-18'
step_id: 'S10'
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
     The S10 and 2026-07-18-user-docs-localization-plan placeholders are machine-filled by
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
     The Translate the how-to section catalogues to Spanish with full-page domain context and ## Scope

- `docs/locales/es` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Translate the how-to section catalogues to Spanish with full-page domain context

## Scope

- `docs/locales/es`

## Description

- Translate the how-to section catalogues to Spanish with full-page domain context, worked by the translation agents across batched commits.
- Spanish-stem AEAT nouns (modelo, casilla, censo, justificante) kept invariant; a follow-up fix kept the generated `(secret)`/`(derived)` markers literal in es.

## Outcome

The how-to `docs/locales/es/LC_MESSAGES/how-to/**` catalogues are fully translated. Delivered across 13 commits tagged `W02.P03.S10` (representative: b2eef0e7aa, 0cde8bc919, 5806a57a4b) plus the marker fix 472a3e94bc under S11. Verified at HEAD as part of the es language reaching 2994/2994 entries with zero untranslated and zero fuzzy.

## Notes

Evidence reconstructed from `git log --oneline --grep "W02.P03.S10"` after delivery; this record closes the step retroactively. No source or code changes.
