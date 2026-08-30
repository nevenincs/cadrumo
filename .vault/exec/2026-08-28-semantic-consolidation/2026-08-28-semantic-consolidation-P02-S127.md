---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-30'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:90500d816ae75e58658e2edbe0d36b36b386af644367bbc0fbbe216b1492616b'
step_id: 'S127'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Adopt the canonical non-negative and positive decimal aliases on the catalogue invoice payload's money and rate fields

## Scope

- `src/cadrumo/core/text_bounds.py`
- `src/cadrumo/entrypoints/cli/`

## Changes

- `M` `src/cadrumo/core/text_bounds.py`
- `M` `src/cadrumo/entrypoints/cli/_ledger_catalogue_invoice_payloads.py`
- `verify:` `pytest src/cadrumo/entrypoints/cli/tests/test_cli_payload_constraint_authority.py src/cadrumo/domain/invoices -n 0 -m ""` -> `pass` (384)

## Notes

`PositiveDecimal` is declared separately from `NonNegativeDecimal` rather than
folded into it, because the difference is the whole point at these sites: an
exchange rate of zero is not a rate, while a total of zero is a legitimate
total. Probed both ways round.
