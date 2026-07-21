---
tags:
  - '#exec'
  - '#ledger-latency-budget'
date: '2026-07-06'
modified: '2026-07-06'
step_id: 'S20'
related:
  - "[[2026-07-06-ledger-perf-optimization-plan]]"
---

# Add source diagnostic fields or message helpers for summarized OUTSIDE_PERIOD counts

## Scope

- `src/aeat/application/aggregation/_source_mesh.py and src/aeat/application/aggregation/tests/test_source_mesh.py`

## Description

- Search the source-mesh diagnostic model for summarized out-of-window support.
- Read `CalculationSourceDiagnostic`, source-mesh exports, and existing source-mesh tests before editing.
- Expand the S20 plan scope to include focused source-mesh tests.
- Add structured `out_of_window_*` fields to `CalculationSourceDiagnostic`.
- Add helper functions for the standard summary message and source diagnostic.
- Add tests for the helper, incomplete summary rejection, and reversed date-span rejection.
- Run source-mesh ruff checks and the full source-mesh unit test file.
- Audit the change and record that no open findings remain.

## Outcome

`CalculationSourceDiagnostic` can now carry a structured out-of-window summary: count, minimum filing date, and maximum filing date. `_source_mesh.py` also exports `out_of_window_summary_message` and `out_of_window_summary_source_diagnostic` for resolver use. The full source-mesh unit test file passed.

## Notes

The first ruff pass found only an import-order issue in the test file; `ruff --fix` corrected it. The final ruff check passed, and `test_source_mesh.py` passed with `24 passed`.
