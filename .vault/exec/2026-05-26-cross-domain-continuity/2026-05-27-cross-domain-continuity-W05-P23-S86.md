---
step_id: S86
date: 2026-05-27
modified: '2026-05-27'
tags:
  - "#exec"
  - "#cross-domain-continuity"
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
decision: hybrid-store-fx-on-transaction
---

# cross-domain-continuity W05.P23.S86 — FX conversion strategy decision

## Decision: Option (c) — Hybrid storage on Transaction

### Chosen approach

Store both `fx_rate: Decimal | None` and `value_in_eur: Decimal | None` on
`Transaction` (not on `RawTransaction`). The import path applies the
`CurrencyNormalizationService` at ingest time and writes the converted values
into the `Transaction` record. Aggregation layers consume `value_in_eur` when
present and the raw currency is not EUR, instead of rejecting the row with
`UNSUPPORTED_CURRENCY`.

### Options considered

(a) **On-import conversion only** — import path converts and stores
`value_in_eur`; raw currency column is discarded for aggregation purposes.
Rejected: the raw amount is a provenance record; discarding the native
currency relationship breaks audit round-trips.

(b) **On-aggregation conversion** — store only the raw foreign-currency
amount; aggregation converts at query time. Rejected: requires a live rate
provider in the aggregation layer, adds non-determinism to casilla
computations, and introduces a provider-dependency on a latency-sensitive
path. Also forces every aggregator to carry its own rate-lookup, undoing the
shared-predicate goal of S89.

(c) **Hybrid (chosen)** — store `fx_rate` and `value_in_eur` alongside the
raw amount at import time. Aggregation reads the pre-converted value.

Rationale for hybrid over (a)/(b):

- The domain already exposes `CurrencyNormalizationService` and
  `ExchangeRateProvider` in `src/aeat/domain/currency/`. Routing the import
  path through this service costs nothing architecturally.
- `value_in_eur` being on `Transaction` (not `RawTransaction`) respects the
  boundary: raw is the verbatim upstream record; the derived EUR value is a
  domain enrichment, exactly like `iva_category` on the same model.
- Pre-converting at import means deterministic, reproducible casilla sums.
  Re-opening a filing period gives the same EUR totals even if the ECB rate
  has moved, because the rate is frozen in the record at import time.
- Aggregation code stays simple: `transaction.value_in_eur or transaction.raw.amount`
  with a `None`-guard, rather than a late-binding async call per row.

### AEAT / BOE FX-date authority

**IVA (Art. 79.Dos LIVA, BOE-A-1992-28740 y modificaciones):**
The taxable base for foreign-currency supplies must be converted to EUR at
the ECB reference rate published on the *devengo* date (the tax point). For
goods: the delivery date. For services: the completion date. In the absence
of a specific devengo, the invoice date is the regulatory proxy.

The ECB publishes daily reference rates (the "EXR" data series) for ~40
currencies. The BOE Circular 4/2015 of Banco de España confirms the ECB
reference rate as the accepted conversion basis for IVA declarations.

**IRPF (Art. 14 LIRPF, Ley 35/2006 BOE-A-2006-20764):**
Foreign income is converted at the exchange rate on the *exigibilidad* date
(the date the income became legally due), not the receipt date. For
self-employment (`actividades económicas`) the criterion mirrors the IVA
devengo: the tax point date, which in practice is the invoice date.

**IS (Impuesto sobre Sociedades, Art. 16.5 LIS, Ley 27/2014 BOE-A-2014-12328):**
Monetary items denominated in foreign currency must be translated at the
closing rate of the tax period for balance-sheet items. Transactional items
(revenue, expense) use the rate at the date of the transaction.

**Practical implementation date choice:**
`value_date` if present, else `booked_date` — matching the existing
`operation_date` computation already applied in every aggregation gate
(`_classify_iva_transaction` line 388, `_classify_renta_transaction`, etc.).
This is the closest proxy available from bank statement data to the
regulatory *devengo* / *exigibilidad* date.

### Where `fx_rate` / `value_in_eur` live

On `Transaction` (not `RawTransaction`) for the same reason `iva_category`
and `counterparty_eu_member_state` live there: these are domain enrichments
derived at import / classification time, not upstream verbatim fields.

The plan description says `_raw_transaction.py` as the target for S87; after
reviewing the boundary design, the correct location is `_models.py`
(`Transaction`). `RawTransaction` is the verbatim upstream record and must
not carry derived fields.

### Implementation sketch (carried into S87-S90)

- S87: Add `fx_rate: Decimal | None = None` and `value_in_eur: Decimal | None = None`
  to `Transaction` in `_models.py`; add them to `_TRANSACTION_DECIMAL_KEYS` for
  coercion; add a `model_validator` that enforces coupling (both `None` or both
  non-`None`; `value_in_eur` must be `None` when currency is EUR).
- S88: Thread an optional `CurrencyNormalizationService` through the
  transaction-catalogue builder / import-service boundary so the import path
  can populate `fx_rate` and `value_in_eur` for non-EUR rows.
- S89: Extract `is_non_eur(transaction)` predicate to
  `src/aeat/application/aggregation/_currency_predicates.py`; replace the
  three `if transaction.raw.currency != "EUR": ...` guards with
  `if is_non_eur_without_conversion(transaction): ...` (rejects only if
  `value_in_eur` is also absent).
- S90: Regression test in `test_fx_conversion.py` — USD invoice imports at
  ECB 2024-01-15 USD/EUR reference rate (1 EUR = 1.0868 USD →
  1 USD = 0.9201 EUR, published ECB EXR data); asserts `value_in_eur` equals
  amount × rate rounded to 0.01; anti-tautology: mutate the rate, assert
  inequality.
