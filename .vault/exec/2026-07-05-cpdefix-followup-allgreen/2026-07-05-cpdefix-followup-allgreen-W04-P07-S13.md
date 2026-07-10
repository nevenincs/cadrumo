---
tags:
  - '#exec'
  - '#cpdefix-followup-allgreen'
date: '2026-07-05'
modified: '2026-07-05'
step_id: 'S13'
related:
  - "[[2026-07-05-cpdefix-followup-allgreen-plan]]"
---

# Cover unclassified actividad-economica gasto and reviewed exclusion behavior with real aggregation tests

## Scope

- `src/aeat/application/aggregation/tests/test_renta_gasto_aggregation.py`

## Description

- Added `irpf_category` support to the real `_gasto_transaction` test helper.
- Added a regression where an outgoing row with `irpf_category=actividad_economica`, `business_classification=NOT_YET_PROCESSED`, and a declared `taxable_base` flows into M130 casilla 02 while an otherwise identical untagged row does not.
- Added a reviewed-exclusion regression proving `BusinessClassification.REVIEWED_EXCLUDED` remains a final filing exclusion even if the row carries the activity IRPF category.
- Updated `src/aeat/application/aggregation/_renta_gasto_ledger.py` so the gasto pipeline mirrors the income-side activity category gate and short-circuits reviewed exclusions before category admission.

## Outcome

- The M130 gasto path now admits explicitly tagged activity expenses before the broader business-classification sweep has run.
- The fix preserves the existing no-noise behavior for untagged unclassified outgoing rows and preserves final reviewed exclusions.

## Notes

- No fake repositories, monkeypatches, skips, xfails, or test-local business logic were introduced. The tests exercise the real `Transaction` model, `TransactionCatalogue`, and `aggregate_renta_gasto_ledger`.
