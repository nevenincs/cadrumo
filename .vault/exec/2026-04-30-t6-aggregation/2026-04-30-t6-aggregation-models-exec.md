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

# t6-aggregation models execution

Implemented the strict boundary models for the accepted T6 contract:

- `PeriodKind` and `Period` parse `YYYY-Qn`, `YYYYQn`, `YYYY-MM`, and `YYYY`, expose inclusive `start` / `end` dates, and reject ambiguous input through `AggregationPeriodError`.
- `CasillaProvenance` carries the casilla id, contributing transaction ids, subtotal, and optional category id.
- `CasillaAggregation` carries the modelo code, parsed period, casilla value mapping, and provenance ledger.

Verification:

- `test_period_accepts_quarter_with_dash_and_is_frozen`
- `test_period_rejects_ambiguous_text`
- JSON schema round-trip coverage through the CLI schema registry.
