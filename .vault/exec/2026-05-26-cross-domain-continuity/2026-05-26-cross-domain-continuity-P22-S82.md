---
tags:
  - "#exec"
  - "#cross-domain-continuity"
date: 2026-05-27
modified: '2026-05-27'
step_id: S82
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# cross-domain-continuity P22.S82

## Outcome

Created `src/aeat/application/aggregation/_renta_income_ledger.py`:

Implements cumulative year-to-date income aggregation for M130 pagos fraccionados
(RD 439/2007 art. 110.2). The quarterly period token is required; the cumulative
window is `[Jan 1, year] → [last day of Qn, year]`.

Key types:
- `RentaIncomeLedgerAggregationIssueReason` (StrEnum) — UNSUPPORTED_DIRECTION,
  UNSUPPORTED_CURRENCY, UNCLASSIFIED_BUSINESS_STATE, PERSONAL_TRANSACTION,
  OUTSIDE_PERIOD, UNSUPPORTED_PERIOD
- `RentaIncomeLedgerAggregationIssue` — traceable exclusion record
- `RentaIncomeObservation` — carries `transaction_id`, `target_casilla="01"`,
  `gross_amount`, `filing_date`; satisfies `RentaIncomeObservationProtocol`
- `RentaIncomeLedgerAggregation` — strict/frozen pydantic model, cross-validated
  `modelo`/`period` against `casilla_aggregation`

Functions:
- `aggregate_renta_income_ledger_from_repositories(*, bucket_id, period, ...)` — loads repo
- `aggregate_renta_income_ledger(transactions, *, bucket_id, period)` — pure aggregator
- `_resolve_quarterly_period(period)` — rejects non-QUARTERLY periods with
  `aggregation.renta_ledger.errors.quarterly_period_required`
- `_classify_income_transaction(transaction, ...)` — INCOMING + EUR + BUSINESS/MIXED filter
- `_income_business_amount(transaction)` — returns `abs(amount)` for BUSINESS,
  `abs(amount) * business_pct` for MIXED; None otherwise
- `_income_casilla_aggregation(period, observations)` — builds `CasillaAggregation`
  with `modelo="130"` and grouped `CasillaProvenance` rows

188 aggregation tests pass. Ruff clean, pyright 0 errors.

## Commit

`3445eb6cf` — S81+S82: M130 actividad-economica income aggregation resolver + ledger module
