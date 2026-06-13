---
tags:
  - '#plan'
  - '#modelo-130-pagos-fraccionados-carry'
date: '2026-06-13'
modified: '2026-06-13'
tier: L2
related:
  - '[[2026-06-13-modelo-130-pagos-fraccionados-carry-adr]]'
  - '[[2026-06-13-first-filer-attestation-adr]]'
  - '[[2026-06-10-calculation-aggregation-taxonomy-adr]]'
  - '[[2026-05-19-modelo-130-relation-regression-adr]]'
  - '[[2026-06-04-m130-casilla-15-override-adr]]'
  - '[[2026-04-27-modelo-130-calc-verify-adr]]'
---








# `modelo-130-pagos-fraccionados-carry` `casilla 05 cumulative pagos-fraccionados carry (target-relative same-ejercicio expanding span)` plan

### Phase `P01` - Selector-grammar: target-relative expanding-span mode

Extend _PreviousModeloSelector with a target-relative prior-quarter expanding-span mode (2T to {1T}, 3T to {1T,2T}, 4T to {1T,2T,3T}) that emits the full preceding-quarter anchor set into the existing multi-anchor aggregation sum resolve path, validated against existing selector validation and the relation-source collision gate.



- [x] `P01.S01` - check git status for peer WIP, then add a target-relative prior-quarter expanding-span selector mode to _PreviousModeloSelector that resolves to all same-ejercicio quarters strictly preceding the target (2T to {1T}, 3T to {1T,2T}, 4T to {1T,2T,3T}), bounded by max_year_delta 0, emitting a tuple of (year_delta, period) anchors into the existing required_period_anchors_for_target path; `src/aeat/domain/calculations/registry/_bindings_previous_filing.py`.
- [x] `P01.S02` - extend _PreviousModeloSelector model validation so the new span mode is mutually exclusive with period, source_periods, and source_period_offset_from_target and stays a direct previous_filing binding under _is_direct_previous_filing_binding, then verify the relation-source collision gate validate_slot_source_hygiene accepts the new mode without a carve-out; `src/aeat/domain/calculations/registry/_bindings_previous_filing.py`.
- [x] `P01.S03` - add a selector unit test asserting the expanding-span mode emits the correct anchor set per target (1T empty, 2T={1T}, 3T={1T,2T}, 4T={1T,2T,3T}) and that the collision gate plus _is_direct_previous_filing_binding classify it as a direct previous_filing binding, computing expected anchors by an independent enumeration not the selector method under test; `src/aeat/domain/calculations/registry/tests/test_bindings_previous_filing.py`.

### Phase `P02` - Registry binding: flip casilla 05 manual to bound

Flip M130 casilla 05 from input_kind manual to bound with the new span binding; encode casilla 05 = sum max(0, prior 07_q) minus sum prior 16_q per the AEAT instrucciones (the positive-part rule and the casilla-16 minoracion are load-bearing); ground the binding source_citations in the verbatim instrucciones text.

- [x] `P02.S04` - check git status for peer WIP on the M130 registry, then flip casilla 05 from input_kind manual to bound and add the previous_filing span binding selecting source_modelo 130 with the new expanding-span mode, carrying raw prior casilla 07 and casilla 16 anchors with aggregation op sum; `src/aeat/_data/registry/aeat/modelos/130/revisions/2019-y-siguientes/bindings/0001-bindings.toml`.
- [x] `P02.S05` - author the casilla 05 registry formula computing sum of per-quarter max(0, prior 07_q) minus sum of prior 16_q (positive-part per quarter before summing, minoracion subtracted), preserving the carried prior-filing values unmodified (shape 2a); `src/aeat/_data/registry/aeat/modelos/130/revisions/2019-y-siguientes/formulas/0001-formulas.toml`.
- [x] `P02.S06` - ground the casilla 05 binding and formula source_citations in the verbatim AEAT instrucciones casilla-05 definition with required_text drawn from the suma-de-las-cantidades-positivas-casilla-07-minorada-casilla-16 quote, per registry-calculation-legal-grounding; `src/aeat/_data/registry/aeat/modelos/130/revisions/2019-y-siguientes/bindings/0001-bindings.toml`.
- [x] `P02.S07` - confirm casilla 07 formula (07 = 04 - 05 - 06) is unchanged and now reads a populated bound casilla 05, then verify casilla 05 no longer over-states the resultado on a cumulative 2T, 3T, and 4T calculate via a registry-load behaviour assertion; `src/aeat/_data/registry/aeat/modelos/130/revisions/2019-y-siguientes/formulas/0001-formulas.toml`.

### Phase `P03` - First-filer / alta-quarter boundary reconciliation

Reconcile the expanding-span candidate-quarter set with the first-filer activity-start authority and deadline-engine pre-alta suppression: alta-containing quarter is the first owed quarter, span starts strictly after it; empty span (1T / alta quarter) materialises casilla 05 = 0 absent-by-design, null-not-error; coverage validator treats empty span as satisfied; casilla-16 filed-zero vs not-captured advisory.

- [x] `P03.S08` - intersect the expanding-span candidate-quarter set with the periods for which a filing obligation actually existed, reading the operator-declared activity_start_date axis (the same field the deadline engine consumes for pre-alta suppression) so the alta-containing quarter is the first owed quarter and the span starts strictly after it, per the first-filer-attestation authority; `src/aeat/domain/calculations/registry/_bindings_previous_filing.py`.
- [x] `P03.S09` - materialise casilla 05 as a clean Decimal zero with the absent-by-design provenance marker when the span is empty (true 1T, first-filer first quarter, or alta quarter), null-not-error, mirroring the casilla-15 1T path; `src/aeat/domain/calculations/registry/_bindings_previous_filing.py`.
- [x] `P03.S10` - teach the observation-coverage validator to treat an empty span as satisfied (not a missing required observation) so a first filer fires no blocker, extending previous_filing_observation_requirements anchor derivation; `src/aeat/domain/calculations/registry/_validate_previous_filing_sources.py`.
- [x] `P03.S11` - encode the casilla-16 filed-zero-vs-not-captured distinction: a prior observation carrying casilla 16 = 0 is a no-op, a prior observation lacking any casilla-16 entry lets the carry proceed but raises a non-blocking advisory naming the gap, never silently dropping the minoracion; `src/aeat/application/modelo/_prior_payment_advisory.py`.

### Phase `P04` - Verification, regression, and advisory degradation

Non-tautological oracle gates: AEAT instrucciones accumulation identity on a multi-quarter fixture (with a negative prior 07 contributing 0 and a non-zero casilla 16) asserted via a different code path than the binding; first-quarter-fires-nothing; coverage-validator-treats-empty-span-as-satisfied; casilla-15 single-offset carry non-regression; Stage-1 prior_payment_not_deducted advisory degrades to fire only when the carry genuinely could not run.

- [x] `P04.S12` - build a multi-quarter M130 fixture (prior 1T/2T/3T filings with chosen ingresos/gastos including at least one quarter whose casilla 07 is negative and at least one non-zero casilla 16), let the engine produce each prior 07 and 16, and assert the 4T casilla 05 equals sum max(0,07_q) minus sum 16_q computed from the AEAT instrucciones rule via an independent helper, a different code path than the span binding under test, per no-tautological-calculation-tests; `src/aeat/application/calculations/tests/test_modelo_130_casilla_05_carry.py`.
- [x] `P04.S13` - add the first-quarter-fires-nothing case: assert a 1T (and a first-filer/alta first quarter) produces casilla 05 = Decimal zero with absent-by-design provenance and emits no blocker and no prior-payment advisory; `src/aeat/application/calculations/tests/test_modelo_130_casilla_05_carry.py`.
- [x] `P04.S14` - add the coverage-validator-treats-empty-span-as-satisfied case: assert previous_filing_observation_requirements emits no required observation for an empty span and the cross-period gate returns clean for a genuine first filer; `src/aeat/domain/calculations/registry/tests/test_validate_previous_filing_sources.py`.
- [x] `P04.S15` - add a parity-style regression proving the casilla-15 single-offset op=copy carry and the casilla-05 expanding-span op=sum carry both resolve correctly on a shared multi-quarter fixture, so the selector extension does not regress the modelo-130-relation-regression guarantees; `src/aeat/application/calculations/tests/test_modelo_130_carry_forward_continuity.py`.
- [x] `P04.S16` - assert the Stage-1 prior_payment_not_deducted advisory degrades to fire only when a prior filing exists in the catalogue but its observation is unreadable/absent so the carry could not populate, and stays silent when the span binding resolves casilla 05 cleanly to non-zero; `src/aeat/application/modelo/tests/test_modelo_130_prior_payment_advisory.py`.

## Description

This plan implements Stage 2 of the Modelo 130 pagos-fraccionados carry
ratified by the modelo-130-pagos-fraccionados-carry ADR (accepted
2026-06-13). Stage 1 already shipped the non-blocking
prior_payment_not_deducted advisory; Stage 2 computes casilla 05
automatically so a cumulative 2T/3T/4T calculate stops over-stating the
resultado.

Casilla 05 ("Pagos fraccionados anteriores") is the same-ejercicio
deduction that carries prior-quarter payments forward. Per the verbatim
AEAT instrucciones, for a target quarter N within ejercicio Y, casilla
05(N) is the sum over prior quarters q before N of max(0, casilla 07_q)
minus the sum over the same q of casilla 16_q. The positive-part rule
(a negative prior 07 contributes 0, not its negative value) and the
casilla-16 minoracion are load-bearing terms; neither may be dropped.
The quantity is a cumulative recurrence over a target-relative span of
prior quarters that shrinks and grows with the target period
(2T to {1T}, 3T to {1T,2T}, 4T to {1T,2T,3T}) - which the existing
previous_filing carry primitive cannot express today.

Per the ADR's chosen Option B, the work generalises `_PreviousModeloSelector`
with a target-relative prior-quarter expanding-span mode that emits the
full preceding-quarter anchor set into the existing multi-anchor
`aggregation = { op = "sum" }` resolve path (the primitive already sums
over anchors; the gap is the target-relative span). The carry stays a
direct previous_filing binding (same canonical mechanism as the casilla-15
saldo-negativo carry), so it clears the relation-source collision gate
without a carve-out. M130 casilla 05 then flips from input_kind manual to
bound; casilla 07 (07 = 04 - 05 - 06) is unchanged and reads the populated
casilla 05.

The empty-span case (true 1T, a first-filer first quarter, or a mid-year
alta quarter) materialises casilla 05 as a clean Decimal zero through the
absent-by-design path - null-not-error - and the observation-coverage
validator treats the empty span as satisfied. Per the ratified mid-year-alta
boundary, the alta-containing quarter is the first owed quarter and the
span starts strictly after it, bound to the first-filer-attestation
activity-start authority (the operator-declared `activity_start_date` axis
the deadline engine already consumes for pre-alta suppression). Casilla 05
is carry-only / not operator-overridable in this work; a manual override is
a future ADR if needed.

## Steps

The Step rows are authored under the `### Phase` blocks above (P01 through
P04). This tier (L2) groups Steps beneath Phases.

## Parallelization

The phases carry hard ordering and are not freely parallelisable. P01
(the selector-grammar extension) is the foundation: P02, P03, and P04 all
consume the new expanding-span mode and cannot land before it. P02 (the
registry binding flip) depends on P01 and must precede P04's value-oracle
gates, which assert on the bound casilla 05. P03 (first-filer / alta
boundary) layers the activity-start intersection onto the span produced by
P01 and the empty-span path consumed by P02; its steps interlock with the
casilla-15 absent-by-design precedent and must settle before P04's
first-quarter-fires-nothing and empty-span-satisfied gates can be trusted.
P04 (verification) is last and gates the whole plan.

Cross-campaign ordering: this plan and the first-filer-attestation plan
both touch the cross-period / previous_filing surface. P03.S08 reads the
operator-declared activity_start_date axis and intersects the span with the
owed-quarter set - the same axis first-filer-attestation scopes its
cross-period requirement graph on. The two campaigns share
`_bindings_previous_filing.py` and the cross-period requirement-derivation
path, so they MUST NOT execute their shared-file steps concurrently. Each
Step that touches a contended file (`_bindings_previous_filing.py`,
`_validate_previous_filing_sources.py`, the M130 registry, and the
prior-payment advisory) checks `git status` per file before its first edit
and aborts on non-authored WIP.

## Verification

The plan is complete when every Step is closed and the gates below pass.
Each gate is non-tautological per `no-tautological-calculation-tests`: the
value oracle is the verbatim AEAT instrucciones accumulation identity, not
a re-computation of the binding formula under test.

- Accumulation-identity oracle (P04.S12). A multi-quarter M130 fixture
  (prior 1T/2T/3T with at least one NEGATIVE prior casilla 07 and at least
  one NON-ZERO casilla 16) asserts the 4T casilla 05 equals
  sum max(0, 07_q) minus sum 16_q computed by an independent helper - a
  different code path than the span binding. A binding that summed raw 07
  (skipping max-0) or dropped the minus-16 term fails this gate loudly.
- First-quarter-fires-nothing (P04.S13). A 1T (and a first-filer / alta
  first quarter) yields casilla 05 = Decimal zero with absent-by-design
  provenance, no blocker, and no prior-payment advisory.
- Empty-span-satisfied (P04.S14). `previous_filing_observation_requirements`
  emits no required observation for an empty span and the cross-period
  clean-state gate returns clean for a genuine first filer.
- Carry parity / no regression (P04.S15). The casilla-15 single-offset
  op=copy carry and the casilla-05 expanding-span op=sum carry both resolve
  correctly on a shared fixture; the selector extension does not regress the
  modelo-130-relation-regression guarantees.
- Advisory degradation (P04.S16). The Stage-1 prior_payment_not_deducted
  advisory fires only when a prior filing exists but its observation is
  unreadable/absent, and stays silent when the carry resolves casilla 05
  cleanly.
- Selector / collision gate (P01.S03). The new span mode is classified a
  direct previous_filing binding by `_is_direct_previous_filing_binding`
  and accepted by `validate_slot_source_hygiene` without a carve-out.
- Legal grounding (P02.S06). The casilla 05 binding/formula source_citations
  carry the verbatim instrucciones required_text and clear the
  registry-calculation-legal-grounding evidence gate.
- Casilla-16 honesty (P03.S11). A prior observation lacking any casilla-16
  entry raises a non-blocking advisory naming the gap; a filed-zero
  casilla 16 is a silent no-op. The minoracion is never silently dropped.

Per `plan-closure-requires-exec-records`, no Step is marked complete
without a matching exec record. For tier-specific verification cadence, see
the convention ADR authorising this plan via the `related:` frontmatter.
