---
tags:
  - '#exec'
  - '#user-docs-localization'
date: '2026-07-18'
modified: '2026-07-19'
body_hash: 'sha256:fe724e25e6d274eb797129501d18d16d5e459e7ad7d8c5a7f9649f4a807892c0'
step_id: 'S03'
related:
  - "[[2026-07-18-user-docs-localization-plan]]"
---

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
