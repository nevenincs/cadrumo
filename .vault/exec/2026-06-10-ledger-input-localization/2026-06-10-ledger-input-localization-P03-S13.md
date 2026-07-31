---
tags:
  - '#exec'
  - '#ledger-input-localization'
date: '2026-06-12'
modified: '2026-07-17'
body_hash: 'sha256:aca46ed38ea6d72a5e5a404661d86325071fdabd30b7b9a1d304942d14d197e5'
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
