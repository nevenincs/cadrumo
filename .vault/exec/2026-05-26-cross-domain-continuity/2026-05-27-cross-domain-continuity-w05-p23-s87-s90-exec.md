---
step_id: S87
date: 2026-05-27
modified: '2026-05-27'
tags:
  - "#exec"
  - "#cross-domain-continuity"
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-05-27-cross-domain-continuity-W05-P23-S86]]"
commits:
  - 9239692e4
  - 434ed8a18
  - 9ff321c88
---

# cross-domain-continuity W05.P23.S87-S90 — FX conversion schema + implementation + tests

## S87 — Transaction schema (`src/aeat/domain/transactions/_models.py`)

Added `fx_rate: Decimal | None = None` and `value_in_eur: Decimal | None = None`
to `Transaction`.  Both fields are coerced from strings via `_TRANSACTION_DECIMAL_KEYS`.
A `field_validator` rejects negative values.  A `model_validator` enforces the
coupling invariant: both fields must be set or both absent; EUR-native transactions
(``raw.currency == "EUR"``) must carry neither.

## S88 — Import path (`src/aeat/application/ledger/_actions.py`)

Added `_apply_fx_conversion(raw, currency_normalizer)` helper that calls
`CurrencyNormalizationService.normalize()` for non-EUR rows, using
`value_date ?? booked_date` as the ECB-rate lookup date (matching the
operation-date convention already used by every aggregation gate).  Returns
`(fx_rate, value_in_eur)` on success, `(None, None)` when the rate is
unavailable or the currency is EUR.

Threaded an optional `currency_normalizer: CurrencyNormalizationService | None`
parameter through `_evaluate_import_rows` and `import_ledger_transactions`.
The parameter defaults to `None` so existing callers are unaffected; production
callers can inject a real ECB feed provider.

Added import of `CurrencyNormalizationService`, `CurrencyNormalizationStatus`,
and `MonetaryAmount` from `...domain.currency`.

## S89 — Shared currency predicate (`src/aeat/application/aggregation/_currency_predicates.py`)

Created `_currency_predicates.py` with two exports:

- `is_non_eur_without_conversion(transaction)`: returns `True` only when
  `raw.currency != "EUR"` AND `value_in_eur is None`.  Aggregation gates use
  this to decide whether to emit `UNSUPPORTED_CURRENCY` — rows with a
  pre-converted `value_in_eur` pass through the gate.

- `effective_eur_amount(transaction)`: returns `value_in_eur` when set,
  else `raw.amount`.

Replaced the three independent `if transaction.raw.currency != "EUR": ...`
guards in `_iva_ledger.py`, `_renta_ledger.py`, and `_renta_income_ledger.py`
with `if is_non_eur_without_conversion(transaction): ...`.

## S90 — Regression tests (`src/aeat/application/aggregation/test_fx_conversion.py`)

Five tests:

1. `test_usd_import_populates_fx_rate_and_value_in_eur` — real
   `import_ledger_transactions` call with `CurrencyNormalizationService` backed
   by ECB 2024-01-15 USD rate (1.0868 EUR/USD).  Asserts `fx_rate` and
   `value_in_eur = 92.01 EUR`.  Oracle: ECB EXR.D.USD.EUR.SP00.A 2024-01-15.

2. `test_usd_transaction_with_value_in_eur_passes_non_eur_predicate` — confirms
   `is_non_eur_without_conversion` returns `False` when `value_in_eur` is set.

3. `test_usd_transaction_without_conversion_is_flagged` — confirms predicate
   returns `True` when `value_in_eur` is absent.

4. `test_missing_rate_leaves_fx_fields_absent` — a provider returning `None`
   for all rates leaves both `fx_rate` and `value_in_eur` as `None`.

5. `test_anti_tautology_mutated_rate_changes_value_in_eur` — two imports with
   canonical vs mutant (50%) rates produce different `value_in_eur`; proves the
   rate is applied, not ignored.

## Test results

70 domain/transactions + 375 aggregation/ledger tests pass.  5 new S90 tests
pass.  No regressions.
