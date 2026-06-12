---
tags:
  - '#exec'
  - '#ledger-input-localization'
date: '2026-06-12'
step_id: 'S14'
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

# Write real-behavior unit tests for _parse_iso_date applied to invoice_date inputs: assert refusal of 15/01/2026, 01-15-2026, 2026/01/15 with ValueError

## Scope

- `assert acceptance of 2026-01-15`
- `src/aeat/entrypoints/cli/tests/test_common_date_parser.py`

## Description

- Authored `test_common_date_parser.py` driving the real ISO date gate against `invoice_date`-shaped inputs: refuses `15/01/2026`, `01-15-2026`, `2026/01/15`; accepts `2026-01-15`.

## Outcome

Done (commit `aab1b534e`). Verified by this closure pass: the date test module passes (part of the 51-test green run), no mocks/skips/xfail.

## Notes

None.
