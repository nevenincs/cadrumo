---
tags:
  - '#exec'
  - '#ledger-input-localization'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S13'
related:
  - "[[2026-06-10-ledger-input-localization-plan]]"
---




# Write real-behavior unit tests for parse_decimal_amount: assert refusal of 1.000, 1.234,56, NaN, Infinity, -Infinity, 1e3 (InvalidOperation or ValueError)

## Scope

- `assert acceptance of 1000`
- `1234.56`
- `0`
- `assert signed variant accepts -50.00 and non-negative variant rejects -50.00`
- `src/aeat/entrypoints/cli/tests/test_common_decimal_parser.py`

## Description

- Authored `test_common_decimal_parser.py` driving the real `parse_decimal_amount`: refuses `1.000`, `1.234,56`, `NaN`, `Infinity`, `-Infinity`, `1e3`; accepts `1000`, `1234.56`, `0`; signed variant accepts `-50.00`, non-negative variant rejects it.

## Outcome

Done (commit `aab1b534e`). Verified by this closure pass: the decimal test module passes (part of the 51-test green run), no mocks/skips/xfail.

## Notes

None.
