---
tags:
  - '#exec'
  - '#ledger-input-localization'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S03'
related:
  - "[[2026-06-10-ledger-input-localization-plan]]"
---




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
