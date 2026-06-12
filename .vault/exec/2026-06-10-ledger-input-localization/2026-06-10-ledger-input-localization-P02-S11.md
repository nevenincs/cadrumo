---
tags:
  - '#exec'
  - '#ledger-input-localization'
date: '2026-06-12'
step_id: 'S11'
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

# Add format example to cli.ledger.add.amount_help in all four locales via python -m aeat.locales set, modelled on the correct_amount_help pattern

## Scope

- `add format example to cli.app.ledger.payable_invoice.invoice_date_help`
- `cli.app.ledger.collectible_invoice.invoice_date_help`
- `and cli.app.ledger.evidence.invoice_date_help in all four locales`
- `src/aeat/locales/`

## Description

- Added a format example to `cli.ledger.add.amount_help` (decimal, e.g. 1200.50) and to the three `invoice_date_help` keys (payable_invoice, collectible_invoice, evidence — ISO 8601 YYYY-MM-DD, e.g. 2026-01-15) in all four locales via the `aeat.locales` CLI.

## Outcome

Done. Verified at HEAD: `amount_help` and all three `invoice_date_help` keys carry the format example in all four locales.

## Notes

None.
