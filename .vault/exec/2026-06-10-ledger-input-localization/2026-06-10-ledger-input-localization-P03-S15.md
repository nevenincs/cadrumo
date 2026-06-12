---
tags:
  - '#exec'
  - '#ledger-input-localization'
date: '2026-06-12'
step_id: 'S15'
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

# Write real-behavior localised error-payload tests: invoke parse_decimal_amount with a bad input in each of en/es/ca/hu locale contexts and assert each error payload carries label, raw value, and expected-format hint

## Scope

- `invoke _parse_iso_date with a bad date and assert all four locales carry %{label} and %{raw} in the rendered message`
- `src/aeat/entrypoints/cli/tests/test_localised_parser_errors.py`

## Description

- Authored `test_localised_parser_errors.py`: invokes `parse_decimal_amount` with a bad input in each of en/es/ca/hu and asserts each refusal carries label, raw value, and expected-format hint; invokes the ISO date gate with a bad date and asserts all four locales render `%{label}` and `%{raw}`.

## Outcome

Done (commit `aab1b534e`). Verified by this closure pass: the localised-payload module passes across all four locales (part of the 51-test green run), no mocks/skips/xfail.

## Notes

Depends on both P01.S01 (helpers) and P02.S09–S11 (locale keys); both present at HEAD, so the four-locale assertions hold.
