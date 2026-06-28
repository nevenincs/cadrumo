---
tags:
  - '#exec'
  - '#ledger-input-localization'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S14'
related:
  - "[[2026-06-10-ledger-input-localization-plan]]"
---




# Write real-behavior unit tests for _parse_iso_date applied to invoice_date inputs: assert refusal of 15/01/2026, 01-15-2026, 2026/01/15 with ValueError

## Scope

- `assert acceptance of 2026-01-15`
- `src/aeat/entrypoints/cli/tests/test_common_date_parser.py`

## Description

- Authored `test_common_date_parser.py` driving the real ISO date gate against `invoice_date`-shaped inputs: refuses `15/01/2026`, `01-15-2026`, `2026/01/15`; accepts `2026-01-15`.

## Outcome

Done (commit `aab1b534e`). Verified by this closure pass: the date test module passes (part of the 51-test green run), no mocks/skips/xfail.

## Notes

None.
