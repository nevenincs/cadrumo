---
tags:
  - '#exec'
  - '#ledger-input-localization'
date: '2026-06-12'
step_id: 'S02'
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

# Replace the local _parse_decimal/_parse_required_decimal with imports of parse_decimal_amount from _common.py

## Scope

- `use the signed variant for --amount until C1 (ledger-amount-direction) lands`
- `src/aeat/entrypoints/cli/_ledger.py`

## Description

- Removed the local `_parse_decimal`/`_parse_required_decimal` definitions from `_ledger.py`.
- Routed every decimal call site (business-pct, taxable-base, iva-rate, iva-amount) through the `_ledger_support` delegators, which forward to the `_common.py` canonical helpers.
- Wired `ledger_add`'s `--amount` to `_parse_amount_magnitude` (non-negative magnitude), since C1 had landed.

## Outcome

Done. Verified at HEAD: zero local parse definitions in `_ledger.py`; `ledger_add` amount uses the non-negative magnitude parser.

## Notes

Sequencing-note deferral: `ledger_update`'s `--amount` still uses the signed delegator at HEAD; tightening it to the magnitude parser is the C1 (`ledger-amount-direction`) follow-up and is carried as uncommitted peer WIP — intentionally out of C3 scope, not touched here.
