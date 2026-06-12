---
tags:
  - '#exec'
  - '#ledger-input-localization'
date: '2026-06-12'
step_id: 'S09'
related:
  - "[[2026-06-10-ledger-input-localization-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace ledger-input-localization with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.
     step_id is the originating Step's canonical identifier, e.g. S01.

     Related: use wiki-links as '[[YYYY-MM-DD-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add frontmatter fields
     outside the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path. -->

# Add %{label} and %{raw} interpolations to cli.common.errors.invalid_iso_date for en, ca, and hu locales using python -m aeat.locales set so all four locales carry the same interpolation tokens as the existing es string

## Scope

- `src/aeat/locales/`

## Description

- Added the `%{label}` and `%{raw}` interpolation tokens to `cli.common.errors.invalid_iso_date` for the en, ca, and hu locales (es already carried them) via the `aeat.locales` CLI.

## Outcome

Done. Verified at HEAD: all four locales carry `%{label}` and `%{raw}` in `invalid_iso_date`; key parity holds.

## Notes

None.
