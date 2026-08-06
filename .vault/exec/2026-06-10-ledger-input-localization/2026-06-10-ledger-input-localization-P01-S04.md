---
tags:
  - '#exec'
  - '#ledger-input-localization'
date: '2026-06-12'
modified: '2026-07-17'
body_hash: 'sha256:53ccc68ecf835bdb4ae9885e69a2a3a63ba7cad98684e351f2ca04bfd18a4b5b'
step_id: 'S04'
related:
  - "[[2026-06-10-ledger-input-localization-plan]]"
---

# Replace the local _parse_decimal/_parse_required_decimal with parse_decimal_amount from _common.py

## Scope

- `gate both invoice_date parameters (lines 98`
- `197) through _parse_iso_date`
- `src/aeat/entrypoints/cli/_ledger_evidence_cli.py`

## Description

- Removed the local parse definitions from `_ledger_evidence_cli.py`, routing decimals through the canonical helper.
- Gated both `invoice_date` parameters through `_parse_optional_iso_date_str` (the ISO gate over `_parse_iso_date`).

## Outcome

Done (commit `aab1b534e`). Verified at HEAD: zero local parse definitions; both `invoice_date` bindings gated, no raw pass-through.

## Notes

None.
