---
tags:
  - '#exec'
  - '#silent-zero-base-aggregation'
date: '2026-06-20'
modified: '2026-06-20'
step_id: 'S11'
related:
  - "[[2026-06-19-silent-zero-base-aggregation-plan]]"
---




# admit the annual M100 income target in the renta-income source selector and resolver without disturbing the M130 quarterly path, with the build-validation family case

## Scope

- `src/aeat/domain/calculations/registry/_ledger_bindings.py`

## Description

Extended the `ledger_renta_income_aggregation` source to admit the annual M100
income target without disturbing the M130 quarterly path.

- `_RentaLedgerIncomeSelector.modelo` relaxed to `Literal[Modelo.M130, Modelo.M100]`.
- Per-modelo casilla allow-set `_RENTA_INCOME_CASILLAS_BY_MODELO` (M130 -> {01,03},
  M100 -> {0171}); the binding validator checks the target against the selector's
  modelo set.
- Mesh resolver `LedgerRentaIncomeAggregationSourceResolver` routes
  modelo == "100" to the annual aggregator, else the quarterly one.

Files: `src/aeat/domain/calculations/registry/_ledger_bindings.py`,
`src/aeat/application/aggregation/_modelo_bindings.py`.

## Outcome

The build-validation family case and the income binding gates stay green; the
domain resolver folds M100 0171 observations into the live M100 binding (proven by
`test_m100_revision_binds_0171_to_income_source_and_resolves`).

## Notes

The earlier "0171 project-verb collision" concern was disproven: the project verb
uses the formula-runtime path, which tolerates a bound 0171, so no disentanglement
was needed.
