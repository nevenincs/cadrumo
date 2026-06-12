---
tags:
  - '#exec'
  - '#ledger-input-localization'
date: '2026-06-12'
step_id: 'S07'
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

- `src/aeat/entrypoints/cli/_ledger_ratios_cli.py`

## Description

- Removed the local parse definitions from `_ledger_ratios_cli.py`, routing decimals through the `parse_decimal_amount` canonical helper.

## Outcome

Done (commit `aab1b534e`). Verified at HEAD: zero local parse definitions; the module imports and uses the canonical helper.

## Notes

None.
