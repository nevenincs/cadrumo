---
tags:
  - '#exec'
  - '#ledger-invoice-decomposition'
date: '2026-08-06'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:31e248b202c6561adc2acce1aa0cb3f365f9952d893a97b929c0454304a6e722'
step_id: 'S56'
related:
  - "[[2026-08-05-ledger-invoice-decomposition-plan]]"
---

# Join the non-deductible share of a fact's input IVA to the IRPF-deductible cost basis via a new RentaDeductibilityContext.iva_deduction_ratio axis, grounded on the AEAT Manual practico Renta 2024 medico radiologo nota 7 worked example (activity exempt from IVA, no right to deduct), leaving the axis unwired from any production taxpayer-fact source as a named follow-up

## Scope

- `src/cadrumo/domain/renta/_ledger_expenses.py`
- `src/cadrumo/domain/renta/tests/test_ledger_expenses.py`

## Description

- Confirm `evaluate_renta_deductibility`'s `_deductible_basis_amount` reads only `taxable_base` (falling back to `gross_amount`), never `iva_amount`, so a fact's non-deductible-for-IVA input cuota never joined the IRPF gasto.
- Confirm the ledger expense aggregation (`application.aggregation._renta_ledger.aggregate_renta_ledger_expenses`) has no route today to any per-taxpayer IVA-deduction-right signal (no import of `domain.prorrata_register`, no exempt-activity fact) — the shape the fix must respect: a domain-level correctness fix behind an axis nothing production-side populates yet, not a false claim of full end-to-end wiring.
- Add `RentaDeductibilityContext.iva_deduction_ratio: Decimal | None` (bounded `[0, 1]`, default `None`), documented as the fraction of input IVA the activity has a right to deduct for IVA purposes; `None` preserves the historic base-only behaviour, mirroring how `residence_ccaa` shipped as an inert axis pending its own wiring.
- Change `_deductible_basis_amount` to accept the context and, only when `taxable_base`, `iva_amount`, and `iva_deduction_ratio` are all known, add `iva_amount * (1 - iva_deduction_ratio)` to the base — the PGC NRV 12.ª non-recoverable-IVA-is-cost rule. Left untouched when any of the three is absent, so a transaction-only fact (`taxable_base is None`, already IVA-inclusive via `gross_amount`) cannot double-count.
- Add five tests to `test_ledger_expenses.py`: a wholly-exempt-activity case (ratio `0`) grounded on the AEAT Manual practico Renta 2024 medico radiologo caso practico, a fractional prorrata-general case (ratio `0.70`), a full-deduction-right and an unevaluated-default case (both leave the base untouched), and an inert-without-a-base-split case.
- Mutation-prove the fix: back up the file by SHA-256, delete the ratio-driven addition (revert `_deductible_basis_amount` to its pre-fix body), confirm exactly the two grounded addition tests redden and the other 20 stay green, restore from backup, re-verify the SHA-256 matches and the full 22 pass again.

## Outcome

`RentaDeductibleExpenseFact`'s carried `iva_amount` can now join the IRPF-deductible cost when the caller states the activity's IVA-deduction ratio, closing the domain-level formula gap that silently excluded non-deductible input IVA from an exempt or prorrata-rationed taxpayer's gasto regardless of what the caller knew. No production caller populates `iva_deduction_ratio` yet: `aggregate_renta_ledger_expenses` has no source for a per-taxpayer IVA-deduction-right signal today, so the wiring from `domain.prorrata_register.ProrrataRegister` (or an exempt-activity taxpayer fact) into this context remains a separate, named follow-up rather than something this Step could honestly claim to close end-to-end.

## Verification

    uv run --no-sync pytest src/cadrumo/domain/renta/tests/test_ledger_expenses.py -q --no-header
    22 passed in 11.00s

    uv run --no-sync pytest src/cadrumo/domain/renta src/cadrumo/application/aggregation -k "renta" -q --no-header
    185 passed, 6 warnings in 36.59s

Mutation proof (formula reverted to base-only): the same suite showed
`2 failed, 20 passed in 13.33s` — exactly
`test_wholly_exempt_activity_joins_the_full_iva_amount_to_the_deductible_cost` and
`test_prorrata_rationed_activity_joins_only_the_non_deductible_iva_share` failed,
every other test (including the three companion regression tests added alongside
them) stayed green. File restored from the SHA-256-verified backup afterwards;
the restored file's digest matched the pre-mutation digest exactly.

    uv run --no-sync ruff check src/cadrumo/domain/renta/_ledger_expenses.py src/cadrumo/domain/renta/tests/test_ledger_expenses.py
    All checks passed!

## Notes

- Grounding source: AEAT Manual practico de Renta 2024, Parte 1, Capitulo 7, caso practico "determinacion del rendimiento neto derivado de actividad profesional en estimacion directa, modalidad simplificada" (extracted markdown L19807-L19965). The "Gastos" table's "IVA soportado" line (1.600, L19900) and nota (7) (L19946-19947: "Se deduce como gasto el IVA soportado por tratarse de una actividad exenta de este impuesto que no da derecho a deducir las cuotas soportadas") ground the wholly-exempt test's IVA figure; the base amount in that fixture is an arbitrary test value (the manual aggregates a year of gastos corrientes into one IVA figure with no per-purchase base), so only the addition itself, not that specific base+IVA total, is checked against the manual.
- Checked for duplication before writing: the existing manual-oracle fixture for this same caso practico (`modelo-100-2024-estimacion-directa-simplificada.json`) and its two consuming tests (`test_m100_2024_estimacion_directa_manual_worked_example.py`, `test_ledger_income_chain_aeat_exempt_worked_example.py`) already cite nota 7, but both exercise the registry FORMULA chain with casilla `0205` ("IVA soportado") hand-typed as an input — neither drives the ledger-aggregation domain function this Step fixes, so there is no overlap with that prior grounding work.
- Left open, tracked separately: wiring `iva_deduction_ratio` from a real taxpayer-fact source (the prorrata register's resolved percentage, or a wholly-exempt-activity marker) into `aggregate_renta_ledger_expenses`'s `RentaDeductibilityContext` construction. Until that lands, every real ledger-derived Renta expense observation still silently excludes non-deductible input IVA from its gasto for any taxpayer whose activity is not fully VAT-recoverable — the axis exists and is correct, but nothing populates it in production yet.
- Commit blocked at authoring time by a persistent `.git/index.lock` in this shared worktree; the change is staged in the working tree only, pending the lock clearing, per the "hold and stage" discipline (no temp-index workaround).
