---
tags:
  - '#exec'
  - '#ledger-invoice-decomposition'
date: '2026-08-06'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:a5cd8a643bb16a1528c73415ec27e17dfb4d529b9a73ea7da1c34f886a3aa6be'
step_id: 'S58'
related:
  - "[[2026-08-05-ledger-invoice-decomposition-plan]]"
---

# Extend the iva_deduction_ratio wiring to the M130 quarterly gasto path: aggregate_renta_gasto_ledger_from_repositories now resolves the same ratio through the shared _resolve_iva_deduction_ratio, for the same ejercicio, so M130 and M100 cannot diverge on it

## Scope

- `src/cadrumo/application/aggregation/_renta_gasto_ledger.py`
- `src/cadrumo/application/aggregation/tests/test_renta_gasto_aggregation.py`

## Description

- Establish first whether M130's gasto pipeline could reuse `RentaDeductibilityContext` (the M100 shape): it cannot. `_renta_gasto_ledger.py`'s own docstring already states it deliberately does not reuse the M100 first-slice pipeline (invoice-evidence reconciliation, category-profile deductibility, an annual window -- all constraint-shape-divergent from the quarterly cumulative sum); it computes `deductible_amount = transaction.taxable_base * proportion` as a direct sum, with no `RentaDeductibilityContext`/`evaluate_renta_deductibility` machinery at all.
- Confirm the LEGAL premise this direct sum was built on -- "IVA soportado is recovered through Modelo 303 and is not a Renta gasto" -- is the FULL-DEDUCTION case only; LIRPF arts. 28-30 base-imponible deductibility governs the pago fraccionado's gasto determination identically to the annual declaration, so an exempt or prorrata-rationed taxpayer under-claims their M130 gasto by the exact same non-recoverable-IVA share M100 was fixed to fold in, every quarter.
- Reuse (never duplicate) `_renta_ledger._resolve_iva_deduction_ratio` via an intra-package private import -- the same sharing shape `_renta_business_eligibility.renta_expense_business_proportion` already uses between these two sibling modules -- rather than threading a `RentaDeductibilityContext` that does not fit this pipeline's shape.
- Thread the resolved ratio through `aggregate_renta_gasto_ledger_from_repositories` (new `profile_record`/`prorrata_register_repository` keyword-only params, `None` defaults) -> `aggregate_renta_gasto_ledger` -> `_classify_gasto_transaction`, keyed on `period.filing_year` (the SAME ejercicio integer M100 resolves for the same calendar year). The one production caller (`_modelo_bindings.py`'s M130 resolver) needed zero changes.
- Join the non-deductible IVA share into `deductible_base` only when BOTH `transaction.iva_amount` and the ratio are known -- mirroring `domain.renta._ledger_expenses._deductible_basis_amount`'s exact gate, never a new under-declaration-detection design (that stays a separate, undecided question, same as the M100 side).
- Add four end-to-end scenario tests to `test_renta_gasto_aggregation.py`, driven through `aggregate_renta_gasto_ledger_from_repositories` (never a hand-built ratio): the same medico radiologo EXENTO figures and 70%-GENERAL prorrata figures M100's own tests already ground against the AEAT Manual practico Renta 2024 and LIVA art. 104.Uno; a NINGUNA-regime byte-identical control; and a fifth-shaped parity test driving BOTH `aggregate_renta_gasto_ledger_from_repositories` (M130) and `aggregate_renta_ledger_expenses_from_repositories` (M100) against the SAME saved transaction and the SAME seeded register entry in the SAME bucket, proving the two filings resolve to the identical non-deductible share rather than assuming it from the shared-function claim alone.
- No AEAT-published quarterly pago-fraccionado worked example for an exempt or prorrata activity was found (grepped the bundled corpus; none exists) -- the underlying PGC NRV 12.ª / LIVA art. 104.Uno arithmetic was already AEAT-grounded by the S56/S57 annual-side oracles, so this Step tests the WIRING and the cross-modelo arithmetic parity onto that already-grounded formula, per the S15 precedent, rather than manufacturing a new quarterly figure.

## Outcome

M130's quarterly gasto pipeline now resolves the identical `iva_deduction_ratio` M100 resolves, for the identical ejercicio, through the identical function -- so the two filings covering the same tax year structurally cannot diverge on this axis. Confirmed by driving both real repository paths against one shared bucket state (`test_m130_and_m100_resolve_the_same_iva_deduction_ratio_for_the_same_ejercicio`): a 70% GENERAL register entry produces `1063.00` on both the quarterly casilla 02 total and the annual first-slice observation, for equivalent inputs.

This closes the worse-direction half of the finding the M100 Step (`P06.S57`) surfaced but named as out of scope: an exempt or prorrata taxpayer's pago fraccionado over-states their quarterly payment four times a year, before the annual M100 ever has a chance to correct it. That gap is now closed at the source rather than only at the annual reconciliation.

## Verification

```
uv run --no-sync pytest src/cadrumo/application/aggregation/tests/test_renta_gasto_aggregation.py -n 0 -q --no-header
23 passed in 13.59s
```

```
uv run --no-sync pytest src/cadrumo/application/aggregation src/cadrumo/domain/renta src/cadrumo/domain/prorrata_register -n 0 -q --no-header
756 passed, 1 failed, 7 deselected in 61.05s
```

The 1 failure (`test_per_modelo_service.py::test_service_surface_has_no_cli_dependency`) is an import-time `IvaValidationError` ("Axis-A component table diverges from CUOTA_LESS_M303_IVA_CATEGORIES") raised inside `domain/iva/_components.py`, confirmed via `git status`/`git diff --stat` to be a DIFFERENT agent's uncommitted, mid-edit change (+79/-2, unrelated to this Step's files) -- pre-existing tree poisoning from concurrent work, not caused by or related to this change. Not touched.

```
uv run --no-sync pytest src/cadrumo/application/modelo/tests/test_e2e_ledger_m130_quarters_to_m100_annual.py -n 0 -q --no-header -m "unit or integration"
5 passed in 55.27s
```

```
uv run --no-sync ruff format --check src/cadrumo/application/aggregation/_renta_gasto_ledger.py src/cadrumo/application/aggregation/tests/test_renta_gasto_aggregation.py
2 files already formatted
uv run --no-sync ruff check src/cadrumo/application/aggregation/_renta_gasto_ledger.py src/cadrumo/application/aggregation/tests/test_renta_gasto_aggregation.py
All checks passed!
```

Mutation proof against `_renta_gasto_ledger.py` (backed up first, sha256 `53d15142b1b9aab05baa24bc13ce27dad0a21f58c641bcc9507ea64cc3636003`, restored and verified byte-identical after):

```
disable the non-deductible-IVA join (if False and transaction.iva_amount is not None and iva_deduction_ratio is not None)
    reddens exento (expects 9600.00, mutated gives 8000.00), prorrata_register
    (expects 1063.00, mutated gives 1000.00), and the M130/M100 parity test
    (fails on the M130 side first); the NINGUNA byte-identical test stays
    green (correctly -- its own claim is "nothing changes"). The two positive
    tests use DIFFERENT ratios (0 and 0.70) producing DIFFERENT expected
    totals (9600.00 and 1063.00), so a mutation that special-cased only one
    ratio could not pass both -- each is independently load-bearing.
```

## Notes

**Why this was the correct shape rather than forcing the M100 pattern onto M130.** The two pipelines' constraint shapes genuinely diverge (invoice-evidence reconciliation and category-profile evaluation vs a direct cumulative sum), and that divergence was already a deliberate, documented decision before this Step. Sharing the SINGLE fact-resolution function while keeping the two ARITHMETIC implementations separate is the same pattern `renta_expense_business_proportion` already established between these exact two sibling modules -- this Step extends an existing precedent rather than inventing a new one.

**The intra-package private import (`from ._renta_ledger import _resolve_iva_deduction_ratio`) is not a service-imports-via-top-level-reexports violation.** Both modules are submodules of the same `application.aggregation` package; the rule's own text carves out intra-package private imports as fine, and this package already does this for `_shared_issue_reasons`, `_currency_predicates`, and `_grouping`.

**M130 always resolves the PROVISIONAL percentage, never the definitive one**, for the same reason M100 does (recorded on `P06.S57`): at the time a Q1-Q3 pago fraccionado is computed the ejercicio is not yet over, so no definitive percentage could exist even if the resolver preferred it; Q4's cumulative window closes the SAME calendar year M100 will later declare, and both read the SAME provisional entry, so there is no point in the year where the two filings could read different percentages for the same ejercicio.

**Un-owned tree-wide failure, not mine, not fixed.** The single failure across the broader run traces to an unrelated in-flight campaign's uncommitted edit to `domain/iva/_components.py` (task #75 in the shared tracker). Verified by `git status`/`git diff --stat` rather than assumed, then left alone -- fixing another agent's active WIP is out of scope and would risk overwriting work in progress.
