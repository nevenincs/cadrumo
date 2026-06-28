---
tags:
  - '#exec'
  - '#ledger-input-localization'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S06'
related:
  - "[[2026-06-10-ledger-input-localization-plan]]"
---




# Replace the local _parse_decimal/_parse_required_decimal with parse_decimal_amount from _common.py

## Scope

- `src/aeat/entrypoints/cli/_ledger_lifecycle_cli.py`

## Description

- Removed the local parse definitions from `_ledger_lifecycle_cli.py`.
- Imported `parse_decimal_amount` directly from `_common.py` and applied it to the `child-amount` input.

## Outcome

Done. Verified at HEAD: zero local parse definitions; `_ledger_lifecycle_cli.py` imports `parse_decimal_amount` directly from `_common` (line ~39) and uses it for `child-amount` (line ~525).

## Notes

This module consumes the canonical helper directly from `_common` rather than via the `_ledger_support` delegators — the cleanest of the migrated modules.
