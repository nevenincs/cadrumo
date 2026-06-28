---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S55'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
---

# live-iva-compensation-wallet W06.P15.S55

Scope: non-private multiyear filed-history parser coverage.

## Description

- Add `test_multiyear_303_submitted_file_parser_promotes_sanitized_iva_history`.
- Build sanitized Modelo 303 submitted-file page records for 2025 4T, 2026 1T, and 2026 2T.
- Parse the records through the production Sede submitted-file parser.
- Persist the parsed filed observations through the production IVA compensation history repository path.
- Reload profile-local remote IVA state and assert cross-year carry-forward lots.

## Outcome

The filed-history parser now has a non-private multiyear regression that starts at submitted-file bytes and ends at profile-local remote IVA state reload. The test asserts production period keys, generated amounts, available-end amount, two carry-forward lots, and zero unallocated application without using the operator's live tax history.

Verification passed:

- `python -m pytest -q src/aeat/application/live/test_filed_capture_calculation_history.py::test_multiyear_303_submitted_file_parser_promotes_sanitized_iva_history`
- `python -m pytest -q src/aeat/application/live/test_filed_capture_calculation_history.py src/aeat/application/live/test_iva_remote_state_acquisition.py`
- `python -m ruff check src/aeat/application/live/test_filed_capture_calculation_history.py`

## Notes

The first focused run failed only on decimal string formatting because production serializes `Decimal("100.00")` as `"100"`. The assertion was corrected to compare decimal values, and the focused plus broader gates then passed.
