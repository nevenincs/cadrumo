---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: 2026-05-27
modified: '2026-05-27'
step_id: S378
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-05-27-dsl-conditional-predicate-adr]]"
---

# `cross-domain-continuity` `W04.P19.S378`

Five-test anti-tautology suite locking the `implies_nonzero` runtime contract across its four logical states plus a missing-consequent default-zero witness.

Commit: `e5b69a0ac`

- Modified: `src/aeat/application/modelo/test_verification_substance.py`

## Description

Authored five `_evaluate_predicate_expression` tests covering the material-implication truth table:

- `test_predicate_implies_nonzero_holds_when_antecedent_zero` — antecedent `0`, consequent `0`; predicate holds vacuously. Mirrors "cuando C01 sea positivo" — zero antecedent does not engage the implication.
- `test_predicate_implies_nonzero_holds_when_antecedent_negative` — antecedent `-100`, consequent `0`; predicate holds. ADR §C constraint: antecedent test is strictly-positive, not non-zero, so a negative value (even though casillas typically cannot carry negative bases) does not engage the implication.
- `test_predicate_implies_nonzero_holds_when_both_positive` — antecedent `500`, consequent `200`; predicate holds. The happy path for cuota-mínima invariants.
- `test_predicate_implies_nonzero_violated_when_consequent_zero` — antecedent `500`, consequent `0`; predicate violated. The canonical M131 EO cuota-mínima miss case. The ADR D2.2 anti-tautology proof: `all_nonzero(["01", "07"])` would silently pass when C01 is itself zero; this operator does not.
- `test_predicate_implies_nonzero_unknown_consequent_treated_as_zero` — antecedent `500`, consequent absent from the mapping; predicate violated. Locks the `.get(id, Decimal(0))` default-zero convention.

The suite exercises every branch authored in S377 and would fail loudly against the mutation set the ADR D2.2 anti-tautology rationale enumerates.

## Verification

- All five tests pass against the S377 runtime branch.
- Each test has a distinct kill-the-mutant target: zero-antecedent vacuous-truth, negative-antecedent contract, satisfied-implication, violated-implication, missing-consequent default-zero.

## Gate evidence

- G1 no naked env reads: unchanged.
- G2 typed pydantic at boundary: tests use `dict[str, Decimal]` matching the runtime contract.
- G3 user messages via tr(): N/A; test-only.
- G4 no locale yml hand-edits: unchanged.
- G5 no shims: tests build values inline; no fixture growth.
- G6 no tautological tests: each assertion derives from the material-implication truth table, not from re-running the helper.

## References

- ADR: dsl-conditional-predicate-adr §D2 (test plan) + §C (constraints)
- Sibling Steps: S376 (registry register), S377 (runtime branch)
- Surface: tests at `src/aeat/application/modelo/test_verification_substance.py:177-230`.
