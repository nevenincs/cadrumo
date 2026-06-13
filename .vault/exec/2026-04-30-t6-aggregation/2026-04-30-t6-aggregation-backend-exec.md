---
tags:
  - "#exec"
  - "#t6-aggregation"
date: 2026-04-30
modified: '2026-04-30'
related:
  - "[[2026-04-30-t6-aggregation-plan]]"
  - "[[2026-04-30-t6-aggregation-adr]]"
---

# t6-aggregation backend execution

Implemented the in-memory classified-catalogue aggregation backend:

- Filters transactions by inclusive period boundaries using `raw.value_date` or `raw.booked_date`.
- Requires in-period transactions to be classified before they can affect the ledger.
- Skips personal and internal-transfer rows.
- Maps incoming business rows to Modelo 130 casilla `01`.
- Maps deductible outgoing business and mixed rows to Modelo 130 casilla `02`, applying `business_pct` and category-profile deductibility ratios.
- Produces grouped provenance by casilla and category id.
- Defers Modelo 303 until VAT base/rate inputs exist.

Verification:

- `test_modelo_130_aggregation_produces_inputs_and_provenance`
- `test_aggregation_outputs_feed_formula_engine`
- `test_unclassified_in_period_transaction_is_refused`
- `test_m303_is_deferred_until_vat_inputs_exist`
- `test_modelo_130_rejects_monthly_period`
