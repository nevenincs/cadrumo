---
tags:
  - '#exec'
  - '#user-docs-localization'
date: '2026-07-18'
modified: '2026-07-18'
step_id: 'S04'
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
     The S04 and 2026-07-18-user-docs-localization-plan placeholders are machine-filled by
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
     The Scaffold the committed es, ca, and hu per-page catalogue trees via sphinx-intl update from the extracted templates and ## Scope

- `docs/locales` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Scaffold the committed es, ca, and hu per-page catalogue trees via sphinx-intl update from the extracted templates

## Scope

- `docs/locales`

## Description

- Run `sphinx-intl update` from the extracted POT templates to create the committed per-language catalogue trees for `es`, `ca`, and `hu`.
- Confirm one `.po` per source page (gettext non-compact) and commit only the language trees, never the POT templates.

## Outcome

Each language carries 57 `.po` catalogues (171 total), one per authored page, all present and untranslated: 2994 translatable entries per language (8982 total across the three targets). Largest pages: the generated environment-overrides reference (395), profile-setup (129), import-export-and-evidence (112).

## Notes

The catalogues are committed all-untranslated by design; the translation wave drives them to complete. Only the language trees were staged; the POT templates stay gitignored.
