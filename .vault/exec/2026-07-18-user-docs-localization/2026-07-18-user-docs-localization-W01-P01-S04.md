---
tags:
  - '#exec'
  - '#user-docs-localization'
date: '2026-07-18'
modified: '2026-07-19'
body_hash: 'sha256:2fb4f6ffc6228267d26ac965d591e82fa0956c42b1e40ecde805acf500fea284'
step_id: 'S04'
related:
  - "[[2026-07-18-user-docs-localization-plan]]"
---

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
