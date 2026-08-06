---
tags:
  - '#exec'
  - '#minimo-descendientes-eligibility'
date: '2026-08-04'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:a8b9135dbfee66e816f49a0958d170002ae31d11d442a0eb94c32f2e5761a4e3'
step_id: 'S05'
related:
  - "[[2026-08-04-minimo-descendientes-eligibility-plan]]"
---

# Extend the ordinary-eligibility test with the Art. 58.1 cap and the Art. 61 norma 2a exclusion, taking both thresholds as caller-supplied registry parameters, and clear the twelve staging entries the drift gate carries for those parameters, deleting them outright if the consumer is visible to the gate AST scan or re-documenting each against its real consumer if it lands in the application-layer injector instead

## Scope

- `src/cadrumo/domain/contribuyente/family.py`
- `src/cadrumo/application/modelo/_profile_binding.py`
- `src/cadrumo/domain/calculations/registry/tests/test_modelo_100_drift_detection.py`

## Description

## Outcome

The ordinary-eligibility predicate now applies the Art. 58.1 rentas cap and the Art. 61
norma 2a own-return exclusion. Both thresholds arrive as caller-supplied values resolved
from the registry parameters authored in the previous phase, carried in a typed threshold
carrier. No regulatory figure entered Python.

The gate condition holds and is measured across all six revisions: a descendant above the
cap contributes zero to both the estatal and the autonomico aggregates.

The anti-tautology pair is the right shape. Exactly at the ceiling keeps the full minimo
while one euro over yields zero, which a mis-specified comparison operator fails at that
exact boundary. That is a genuine discriminator rather than a restatement of the formula.

The staging debt this campaign created in the previous phase is cleared, and cleared by the
condition the executor itself wrote rather than by a convenient reading of it. The consumer
landed in the application layer, reading revision parameters directly and passing the result
down, exactly as the existing autonomic tranche resolution does. Because that placement sits
outside the drift gate's scan, the twelve entries correctly remain in the staging set and
were re-documented from pending-with-no-consumer to consumed-by-this-named-function, with
the verifying test named. The gate passes at nine. No debt was inherited forward.

A residual the ADR did not anticipate, decided by the executor and recorded here because it
is load-bearing. An UNDECLARED rentas figure does not exclude. Reading absence as
above-the-cap would zero the minimo for every descendant whose figure nobody has entered,
which for a young child is the overwhelming majority, producing a large silent under-claim
and a regression for every existing profile. Absence is therefore non-excluding, while a
PRESENT but unparseable figure refuses rather than falling back, because a silent fallback
would point in the claiming direction and let a typo in a disqualifying figure restore the
full minimo.

That leaves a real and stated residual: a descendant who genuinely earns above the cap, whose
figure was never entered, still over-claims silently. The field now exists and can be
expressed, which it could not before, but only the entry surface closes the gap in practice.
This is recorded rather than resolved and belongs in the closing audit.

## Notes
