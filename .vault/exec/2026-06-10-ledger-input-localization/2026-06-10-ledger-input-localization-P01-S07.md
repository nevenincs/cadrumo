---
tags:
  - '#exec'
  - '#ledger-input-localization'
date: '2026-06-12'
modified: '2026-07-17'
body_hash: 'sha256:51f5b3a6dd84de2e6c2173b2cfb5ce630411789c5b30dffe36eb6eb5dc02125d'
step_id: 'S07'
related:
  - "[[2026-06-10-ledger-input-localization-plan]]"
---

# Replace the local _parse_decimal/_parse_required_decimal with parse_decimal_amount from _common.py

## Scope

- `src/aeat/entrypoints/cli/_ledger_ratios_cli.py`

## Description

- Removed the local parse definitions from `_ledger_ratios_cli.py`, routing decimals through the `parse_decimal_amount` canonical helper.

## Outcome

Done (commit `aab1b534e`). Verified at HEAD: zero local parse definitions; the module imports and uses the canonical helper.

## Notes

None.
