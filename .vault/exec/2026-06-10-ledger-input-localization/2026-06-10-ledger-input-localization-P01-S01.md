---
tags:
  - '#exec'
  - '#ledger-input-localization'
date: '2026-06-12'
step_id: 'S01'
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

# Author canonical parse_decimal_amount (signed and non-negative variants) and verify _parse_iso_date is already present in _common.py

## Scope

- `add _DECIMAL_RE constant and is_finite() guard`
- `export both helpers via __all__`
- `src/aeat/entrypoints/cli/_common.py`

## Description

- Authored `parse_decimal_amount(raw, *, label, signed=True)` and `parse_optional_decimal_amount(...)` in `_common.py`.
- Added the `_DECIMAL_RE` (non-negative) and `_SIGNED_DECIMAL_RE` (signed) constants with a two-digit fractional cap, plus the `is_finite()` defence-in-depth guard.
- Exported both helpers via `__all__`; confirmed `_parse_iso_date` was already present.

## Outcome

Landed (canonical home reconciled onto the peer-extracted `_common.py`; hardened by commit `aab1b534e`). Verified at HEAD: both helpers present with both regex variants, the `is_finite()` guard, and the `__all__` export; the localised `cli.ledger.errors.invalid_decimal` refusal carries label and raw.

## Notes

Closure-pass verification only; production code landed in a prior session. No new code authored by this pass.
