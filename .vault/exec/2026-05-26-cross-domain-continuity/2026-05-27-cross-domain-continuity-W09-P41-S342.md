---
step_id: S342
tags:
  - "#exec"
  - "#cross-domain-continuity"
date: 2026-05-27
modified: '2026-05-27'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-05-27-cross-domain-continuity-w09-p41-s322-s334-exec]]"
---

# cross-domain-continuity W09.P41.S342 — M130 income aggregation actividad-económica fix

## Outcome

S342 closed. M130 casilla 01 now correctly aggregates income from transactions
tagged `irpf_category=actividad_economica` even when
`business_classification=NOT_YET_PROCESSED`.

## Root cause

`_income_business_amount` evaluated `business_classification` exclusively. A
transaction carrying `irpf_category=actividad_economica` before the
classification sweep had run returned `None`, suppressing its contribution to
the cumulative window and producing casilla 01 = 0.00.

## Fix

Added an `irpf_category == _IRPF_CATEGORY_ACTIVIDAD_ECONOMICA` early-exit
branch in `_income_business_amount` that returns `abs(transaction.raw.amount)`
directly, treating the explicit IRPF category as the authoritative M130
eligibility gate without requiring `business_classification` to have been set.

## Files changed

- `src/aeat/application/aggregation/_renta_income_ledger.py` — irpf_category
  bypass branch; corrected `__all__` (removed private names). Cross-authored
  with peer WIP: TRABAJO_INCOME exclusion reason, taxable_base_amount field on
  RentaIncomeObservation, trabajo exclusion filter, `_IRPF_CATEGORY_*` constants.
- `src/aeat/domain/calculations/registry/_bindings.py` — peer WIP committed
  forward: `taxable_base_sum` selector/resolver/protocol updates,
  `_RENTA_130_INCOME_CASILLAS` now includes "03".
- `src/aeat/_data/registry/aeat/modelos/130/revisions/2019-y-siguientes/bindings/0003-m130-income-cumulative.toml` —
  new `modelo-130-actividad-economica-ingresos-taxable-base-cumulative` binding
  targeting casilla 01 via `taxable_base_sum` fact.
- `src/aeat/application/aggregation/test_renta_income_aggregation.py` — 6 new
  regression tests: irpf_category eligibility gate, trabajo exclusion,
  taxable_base_amount observation field, anti-tautology proof.

## Tests

14 income aggregation tests pass (8 pre-existing + 6 new). M130 registry
binding tests pass. Ruff lint clean on all modified Python files.

## Commit

`2a795bacd` — S342: M130 actividad-económica income aggregation fix + taxable_base_sum path

## Gates

- G1 ruff: clean
- G2 mypy: not run (pre-existing mypy issues in codebase)
- G3 pytest (unit): 14/14 income aggregation tests pass
- G4 registry binding tests: pass
- G5 cross-authorship: documented in commit message
- G6 vault plan step: closed via `vault plan step check`
