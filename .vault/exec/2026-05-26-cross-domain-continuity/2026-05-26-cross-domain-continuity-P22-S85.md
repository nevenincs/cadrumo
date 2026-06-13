---
tags:
  - "#exec"
  - "#cross-domain-continuity"
date: 2026-05-27
modified: '2026-05-27'
step_id: S85
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# cross-domain-continuity P22.S85

## Outcome

Created `src/aeat/application/aggregation/test_renta_income_aggregation.py` with 10 tests:

Pure-aggregator tests (no repository):
- `test_q1_window_includes_jan_mar_transactions` — Q1 window [Jan 1 to Mar 31]; Apr excluded with OUTSIDE_PERIOD
- `test_q2_window_accumulates_jan_through_jun` — Q2 YTD window [Jan 1 to Jun 30]; Jul excluded
- `test_mixed_classification_applies_business_pct` — MIXED at 60% yields 600.00 from 1000.00
- `test_personal_transaction_excluded_with_reason` — PERSONAL emits PERSONAL_TRANSACTION issue
- `test_non_eur_transaction_excluded_with_reason` — USD emits UNSUPPORTED_CURRENCY issue
- `test_outgoing_transaction_excluded_with_reason` — OUTGOING emits UNSUPPORTED_DIRECTION issue
- `test_inactive_transaction_skipped_silently` — ARCHIVED state skipped, no issue record
- `test_non_quarterly_period_raises` — annual period raises AggregationPeriodError

Repository-backed integration (isolated_runtime_profile, real SecureObjectRepository):
- `test_repository_backed_aggregation_emits_casilla_01_sum` — Q1 yields 4000.00 (2500+1500),
  Q2 yields 7000.00 cumulative (2500+1500+3000); verifies q2_only excluded from Q1 with
  OUTSIDE_PERIOD issue

Structural pin:
- `test_casilla_01_target_matches_expected_binding_contract` — every observation targets
  casilla "01", modelo field is "130"

All 10 tests pass. Ruff clean, pyright 0 errors.

## Commit

`dfde39115` — S85: regression tests for M130 actividad-economica income aggregation
