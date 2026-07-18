---
tags:
  - '#exec'
  - '#user-docs-localization'
date: '2026-07-18'
modified: '2026-07-18'
step_id: 'S02'
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
     The S02 and 2026-07-18-user-docs-localization-plan placeholders are machine-filled by
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
     The Implement user-scope gettext POT extraction as a dev.docs build step writing uncommitted templates with gettext_compact disabled and ## Scope

- `dev/docs/build.py`
- `dev/docs/i18n.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Implement user-scope gettext POT extraction as a dev.docs build step writing uncommitted templates with gettext_compact disabled

## Scope

- `dev/docs/build.py`
- `dev/docs/i18n.py`

## Description

- Add the `dev.docs.i18n` module owning gettext extraction and catalogue management, following the sibling `dev/docs` module conventions.
- Implement `extract_pot` running Sphinx's `gettext` builder under `CADRUMO_DOCS_SCOPE=user` over exactly the authored user-scope page set, writing one template per page to the uncommitted `docs/locales/pot/`.
- Implement `update_catalogues` invoking `sphinx-intl update`, and `user_scope_source_pages` as the single definition of the localized surface (imported by the completeness gate so extraction and gate can never disagree).
- Derive `TARGET_LANGUAGES` from `OutputLanguage` minus English.
- Add the `docs/locales/pot/` ignore and the `dev/docs/i18n.py` `S603` lint exemption.

## Outcome

Extraction produces exactly 57 `.pot` templates, one per authored user page, matching the page-set function count. `gettext_compact` disabled so each page owns one catalogue.

## Notes

Extraction excludes the generated CLI reference and `_generated` glossary/casilla trees and the API autodoc tree, matching the ADR's ~57-page translation surface. The 65 build warnings are the expected user-scope generated-link warnings, non-fatal without `-W`.
