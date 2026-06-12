---
tags:
  - '#exec'
  - '#ledger-input-localization'
date: '2026-06-12'
step_id: 'S13'
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

# Write real-behavior unit tests for parse_decimal_amount: assert refusal of 1.000, 1.234,56, NaN, Infinity, -Infinity, 1e3 (InvalidOperation or ValueError)

## Scope

- `assert acceptance of 1000`
- `1234.56`
- `0`
- `assert signed variant accepts -50.00 and non-negative variant rejects -50.00`
- `src/aeat/entrypoints/cli/tests/test_common_decimal_parser.py`

## Description

- Authored `test_common_decimal_parser.py` driving the real `parse_decimal_amount`: refuses `1.000`, `1.234,56`, `NaN`, `Infinity`, `-Infinity`, `1e3`; accepts `1000`, `1234.56`, `0`; signed variant accepts `-50.00`, non-negative variant rejects it.

## Outcome

Done (commit `aab1b534e`). Verified by this closure pass: the decimal test module passes (part of the 51-test green run), no mocks/skips/xfail.

## Notes

None.
