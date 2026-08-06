---
tags:
  - '#exec'
  - '#modelo-verify-nonzero-guards'
date: '2026-06-30'
modified: '2026-07-17'
body_hash: 'sha256:0236413581fd50110ac6772cfeae6fcf0df06b72791371ea20cfa030aa38e77e'
step_id: 'S14'
related:
  - "[[2026-06-30-modelo-verify-nonzero-guards-plan]]"
---

# Add a gate-behaviour test calling evaluate_verification_predicates directly for the M714 cuota-integra-to-total-cuota-integra advisory, proving FIRES on positive-cuota-integra-zero-total, HOLDS on positive-cuota-integra-positive-total, and trivial-HOLD on zero-or-negative-cuota-integra

## Scope

- `src/aeat/application/modelo/tests/test_verification_m714_advisory.py`

## Description

- Create `test_verification_m714_advisory.py`, mirroring the shape of the existing `test_verification_m131_advisory.py` gate-behaviour suite.
- Load the shipped `modelo-714-cuota-integra-implica-total-cuota-integra` predicate off the validated registry authority's 2021-y-siguientes revision and assert its `ADVISORY` finding_kind and exact expression.
- Assert FIRES: positive cuota integra with zero total cuota integra surfaces exactly one `ADVISORY`/`WARNING` finding carrying the `ley-19-1991:art-30` legal ref.
- Assert HOLDS: positive cuota integra with a matching positive total cuota integra produces zero findings.
- Assert trivial-HOLD: a zero (or absent) cuota integra antecedent produces zero findings regardless of the consequent, calling `evaluate_verification_predicates` directly against synthetic casilla-value maps -- no hand-computed Decimal oracle is asserted, per the no-tautological-calculation-tests discipline (this is gate-behaviour, not a calculation-value test).

## Outcome

`uv run --no-sync pytest src/aeat/application/modelo/tests/test_verification_m714_advisory.py -q` passes 4/4: the predicate-shape assertion, the FIRES case, the HOLDS case, and the trivial-HOLD case (covering both an explicit-zero and an absent-casilla map).

## Notes

None.
