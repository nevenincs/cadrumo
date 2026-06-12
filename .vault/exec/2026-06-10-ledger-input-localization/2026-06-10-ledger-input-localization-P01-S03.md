---
tags:
  - '#exec'
  - '#ledger-input-localization'
date: '2026-06-12'
step_id: 'S03'
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

# Replace the local _parse_decimal/_parse_required_decimal with parse_decimal_amount from _common.py

## Scope

- `gate all four invoice_date parameters (lines 180`
- `281`
- `398`
- `503) through _parse_iso_date`
- `src/aeat/entrypoints/cli/_ledger_business_invoice_cli.py`

## Description

- Removed the local parse definitions from `_ledger_business_invoice_cli.py`, routing decimals through the canonical helper.
- Gated every `invoice_date` parameter through the ISO date gate (`_parse_iso_date_str` / `_parse_optional_iso_date_str`, the string-returning wrappers over `_parse_iso_date`).

## Outcome

Done (commit `aab1b534e`). Verified at HEAD: zero local parse definitions; no raw `invoice_date=invoice_date` pass-through survives — both `invoice_date` bindings are gated, closing the F5 unguarded-date defect.

## Notes

The plan named `_parse_iso_date`; the landed code uses the `_str` wrapper variants for the contracts that persist the date as a 10-character string. Same validation (delegates to `_parse_iso_date`), correct typed form — a refinement, not a gap.
