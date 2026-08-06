---
tags:
  - '#exec'
  - '#user-docs-localization'
date: '2026-07-18'
modified: '2026-07-19'
body_hash: 'sha256:bed9cc796cfc73b0a4a5548dca23add7c5d37bf9aad37ffb067a1a74c264212a'
step_id: 'S02'
related:
  - "[[2026-07-18-user-docs-localization-plan]]"
---

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
