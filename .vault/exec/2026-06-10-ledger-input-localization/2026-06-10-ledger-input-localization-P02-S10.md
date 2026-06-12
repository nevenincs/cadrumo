---
tags:
  - '#exec'
  - '#ledger-input-localization'
date: '2026-06-12'
step_id: 'S10'
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

# Append expected-format hint to cli.ledger.errors.invalid_decimal in all four locales (en, es, ca, hu) via python -m aeat.locales set

## Scope

- `hint must name the accepted form: dot decimal separator`
- `no thousands grouping`
- `e.g. 1234.56`
- `src/aeat/locales/`

## Description

- Appended the expected-format hint (dot decimal separator, no thousands grouping, e.g. 1234.56) to `cli.ledger.errors.invalid_decimal` in all four locales via the `aeat.locales` CLI.

## Outcome

Done. Verified at HEAD: all four locales carry the accepted-form hint in `invalid_decimal`, alongside the `%{label}`/`%{raw}` tokens.

## Notes

None.
