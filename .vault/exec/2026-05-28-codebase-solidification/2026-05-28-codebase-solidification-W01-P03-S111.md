---
step_id: S111
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# codebase-solidification W01.P03.S111 — IVA wallet empty-cell SedeParseError translated_message

## Outcome

Verified that both `SedeParseError` raises for empty IVA wallet cells in
`src/aeat/adapters/outbound/aeat/sede/_iva_compensation_wallet.py` already carry
`translated_message=tr(...)`:

- `_wallet_row_from_cells`: empty period cell →
  `translated_message=tr("adapters.sede.errors.iva_wallet_empty_period_cell")`
- `_parse_spanish_decimal`: empty amount cell →
  `translated_message=tr("adapters.sede.errors.iva_wallet_empty_amount_cell")`

Both locale keys exist in all four locale files. No production code changes needed.

## Files touched

- `src/aeat/adapters/outbound/aeat/sede/_iva_compensation_wallet.py` (already correct)

## Verification

`vault plan step check S111` applied. Locale audit clean.
