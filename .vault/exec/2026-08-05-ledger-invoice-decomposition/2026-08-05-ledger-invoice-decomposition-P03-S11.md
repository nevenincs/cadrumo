---
tags:
  - '#exec'
  - '#ledger-invoice-decomposition'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:5377d543946d6648bbfa6554f3aeb5f3fe2e4ccf1c83266d84ff43a48ab43596'
step_id: 'S11'
related:
  - "[[2026-08-05-ledger-invoice-decomposition-plan]]"
---

# Relax the withheld-inference precondition to category-determinable cuota so exempt invoices recover their retencion, keeping the registry max-rate bound

## Scope

- `src/cadrumo/application/aggregation/_renta_income_ledger.py`

## Description

- Replace `_income_withheld_amount` in `src/cadrumo/application/aggregation/_renta_income_ledger.py:588` with a bounded derivation returning a typed `_WithheldInference` (amount plus route).
- Add `_determinable_cuota` at `:569`, reading the Axis-A table for a cuota that is zero by law instead of testing `iva_amount is None`.
- Apply the registry maximum supported rate at the inference site, refusing rather than capping an inference above it.
- Add `LedgerWithholdingDerivation` at `src/cadrumo/core/aggregation.py:516` as a closed value set, beside `LedgerIncomeGrounding`.
- Carry `withheld_derivation` on `RentaIncomeObservation` at `:162`, with a validator refusing a marker that contradicts its figure.
- Promote the RIRPF art. 95 rate loader onto the `domain.transactions` facade, a precondition of the consuming import.
- Add twelve behavioural cases in `src/cadrumo/application/aggregation/tests/test_income_withheld_derivation.py`.

## Outcome

Landed as commit `102d8f6473` (4 files, +529 / -10).

Raw counts, serial runs (`-n 0`): `test_income_withheld_derivation.py` 12 passed; `application/aggregation/tests` 563 passed, 7 deselected; the touched packages together (`application/aggregation/tests`, `test_ledger_renta_income_binding.py`, `domain/transactions/tests`) 743 passed, 7 deselected. Tree-wide `pytest src/cadrumo --collect-only -q` collected 20008 of 23888 with no collection errors. Lint and format clean over the touched files.

The load-bearing finding is that the max-rate bound was NOT where the step assumed. It lives only on the Transaction gross invariant (`src/cadrumo/domain/transactions/_models.py:1173-1200`), which returns early when either `taxable_base` or `iva_amount` is absent. Every row this step newly admits carries no `iva_amount`, so none of them had ever met that bound. Relaxing the precondition without also moving the bound would have produced entirely unbounded inferences on exactly the new path, the opposite of keeping the registry max-rate bound. The bound is therefore applied at the inference site for all routes; for the declared-cuota route it is redundant with the model invariant, which raises at construction, and applying it uniformly means one rule rather than two that must be read together to know whether a row was checked.

An inference above the bound is refused, not capped. Capping would invent a withholding at exactly the legal maximum, which is a fabricated legal fact; the model invariant makes the same choice by raising.

## Notes

The derivation marker was first written with a two-way validator refusing any figure beside a non-derived marker. That broke sixteen existing construction sites across two peer test files, which build the observation with a withheld amount and no marker. The field carries a default, so making that default illegal in combination with a common value was a bad contract rather than a strict one, and the alternative, making the field required and sweeping sixteen sites in files outside this lane, was disproportionate.

The validator was narrowed to the two directions that actually protect meaning: an inference marker sitting on no figure, and a refusal carrying the figure it refused. The `NOT_APPLICABLE` default stays permissive about the amount, which is what an observation built without reference to this axis means. The guarantee that matters is pinned on the production path instead, by `test_the_builder_never_emits_an_unmarked_withholding`.

Two brief premises decayed mid-step. A peer landed the S18 category-and-kind re-key of the Axis-A table while this work was in flight, so `category_cuota_is_zero_by_law` grew a required kind argument; the income path passes the issued kind, since an actividad-economica receipt is the issued side by construction. Before that landed, their working-tree edit left `domain/iva` unimportable for several minutes and broke collection tree-wide, which produced a 140-failure run that was entirely peer breakage and not attributable to this step.

### Mutation proofs

Added under the operator no-vacuous-tests mandate. Each mutation was applied to a file copied aside first, the suite run, then the file restored byte-for-byte from that copy; no mutation reached the index and `grep -c MUTATION` returned 0 on both files afterwards.

- Disable the max-rate bound (replace the `round_to_cents(inferred) > maximum_supported` guard with a dead branch): `test_inference_above_the_supported_rate_is_refused_not_capped` and `test_the_refusal_boundary_is_the_registry_rate_not_a_local_literal` both fail. 2 failed, 10 passed.
- Collapse the untagged / exempt distinction (make `_determinable_cuota` return zero for every absent cuota rather than only for a category whose cuota is zero by law): `test_absent_cuota_without_a_declared_category_stays_unknown` fails. 1 failed, 11 passed.
- Perform the forbidden inversion (reconstruct the base from cash as `cash / (1 - rate)` for a base-less row and emit the difference): `test_row_without_a_base_derives_nothing_rather_than_inverting_a_rate` fails. 1 failed, 11 passed.

The third is the one worth naming: inversion-never is a prohibition, and a prohibition that no test can violate is decoration. The mutation is the exact code a well-meaning later author would write to make more rows recover a retención, and the gate now refuses it.
