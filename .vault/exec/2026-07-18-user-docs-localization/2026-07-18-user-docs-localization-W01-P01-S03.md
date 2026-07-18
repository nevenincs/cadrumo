---
tags:
  - '#exec'
  - '#user-docs-localization'
date: '2026-07-18'
modified: '2026-07-18'
step_id: 'S03'
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
     The S03 and 2026-07-18-user-docs-localization-plan placeholders are machine-filled by
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
     The Wire the Sphinx config to read the build language from an environment switch validated against OutputLanguage, with locale_dirs pointing at the committed catalogue tree and en as default and ## Scope

- `docs/conf.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Wire the Sphinx config to read the build language from an environment switch validated against OutputLanguage, with locale_dirs pointing at the committed catalogue tree and en as default

## Scope

- `docs/conf.py`

## Description

- Import `OutputLanguage` at `docs/conf.py` module level, consistent with the existing module-level `PRODUCT_IDENTITY` core import.
- Replace the pinned `language = "en"` with `language` read from `CADRUMO_DOCS_LANGUAGE` (default `en`), validated against `_VALID_DOCS_LANGUAGES` derived from `OutputLanguage` and raising `ValueError` on an unknown tag.
- Add `locale_dirs = ["locales"]` and `gettext_compact = False`.

## Outcome

The config reads the build language from the environment and refuses any tag outside the `OutputLanguage` set. The CLI output language stays pinned to English at the top of the module (executed sequences render live CLI output as evidence). No second hand-listed language set is introduced.

## Notes

The user-scope no-app-import design governs rendering (autodoc); `conf.py` already imports core modules at module level, so importing `OutputLanguage` there is consistent and does not defeat the scope.
