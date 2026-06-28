---
tags:
  - '#exec'
  - '#ledger-input-localization'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S02'
related:
  - "[[2026-06-10-ledger-input-localization-plan]]"
---




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
