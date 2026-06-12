---
tags:
  - '#exec'
  - '#ledger-input-localization'
date: '2026-06-12'
step_id: 'S12'
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

# Run python -m aeat.locales scaffold --check and python -m aeat.locales audit to confirm zero drift and all four locales remain in key parity with no honesty-ratchet violations

## Scope

- `src/aeat/locales/`

## Description

- Ran `python -m aeat.locales scaffold --check` and `python -m aeat.locales audit`.

## Outcome

Done. Both gates report `ok` for all four locales (ca, en, es, hu): zero drift, full key parity, no honesty-ratchet violations.

## Notes

Gates were run against the working tree, which also carries unrelated peer C1 help-text edits; those are parity-preserving, so the gates stay green.
