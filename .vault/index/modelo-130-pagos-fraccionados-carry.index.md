---
generated: true
tags:
  - '#index'
  - '#modelo-130-pagos-fraccionados-carry'
date: '2026-08-16'
modified: '2026-08-16'
body_schema: 'body-v1'
body_hash: 'sha256:d78a6bc7d500ae473f512b2cd93948a5b33697d223a78859a98e01451050de3c'
related:
  - '[[2026-06-13-modelo-130-pagos-fraccionados-carry-P01-S01]]'
  - '[[2026-06-13-modelo-130-pagos-fraccionados-carry-P01-S02]]'
  - '[[2026-06-13-modelo-130-pagos-fraccionados-carry-P01-S03]]'
  - '[[2026-06-13-modelo-130-pagos-fraccionados-carry-P02-S04]]'
  - '[[2026-06-13-modelo-130-pagos-fraccionados-carry-P02-S05]]'
  - '[[2026-06-13-modelo-130-pagos-fraccionados-carry-P02-S06]]'
  - '[[2026-06-13-modelo-130-pagos-fraccionados-carry-P02-S07]]'
  - '[[2026-06-13-modelo-130-pagos-fraccionados-carry-P03-S08]]'
  - '[[2026-06-13-modelo-130-pagos-fraccionados-carry-P03-S09]]'
  - '[[2026-06-13-modelo-130-pagos-fraccionados-carry-P03-S10]]'
  - '[[2026-06-13-modelo-130-pagos-fraccionados-carry-P03-S11]]'
  - '[[2026-06-13-modelo-130-pagos-fraccionados-carry-P04-S12]]'
  - '[[2026-06-13-modelo-130-pagos-fraccionados-carry-P04-S13]]'
  - '[[2026-06-13-modelo-130-pagos-fraccionados-carry-P04-S14]]'
  - '[[2026-06-13-modelo-130-pagos-fraccionados-carry-P04-S15]]'
  - '[[2026-06-13-modelo-130-pagos-fraccionados-carry-P04-S16]]'
  - '[[2026-06-13-modelo-130-pagos-fraccionados-carry-adr]]'
  - '[[2026-06-13-modelo-130-pagos-fraccionados-carry-plan]]'
  - '[[2026-06-13-modelo-130-pagos-fraccionados-carry-research]]'
---

# `modelo-130-pagos-fraccionados-carry` feature index

Auto-generated index of all documents tagged with `#modelo-130-pagos-fraccionados-carry`.

## Documents

### adr

- `2026-06-13-modelo-130-pagos-fraccionados-carry-adr` - `modelo-130-pagos-fraccionados-carry` adr: `casilla 05 cumulative pagos-fraccionados carry (target-relative same-ejercicio sum)` | (**status:** `accepted`)

### exec

- `2026-06-13-modelo-130-pagos-fraccionados-carry-P01-S01` - check git status for peer WIP, then add a target-relative prior-quarter expanding-span selector mode to _PreviousModeloSelector that resolves to all same-ejercicio quarters strictly preceding the target (2T to {1T}, 3T to {1T,2T}, 4T to {1T,2T,3T}), bounded by max_year_delta 0, emitting a tuple of (year_delta, period) anchors into the existing required_period_anchors_for_target path
- `2026-06-13-modelo-130-pagos-fraccionados-carry-P01-S02` - extend _PreviousModeloSelector model validation so the new span mode is mutually exclusive with period, source_periods, and source_period_offset_from_target and stays a direct previous_filing binding under _is_direct_previous_filing_binding, then verify the relation-source collision gate validate_slot_source_hygiene accepts the new mode without a carve-out
- `2026-06-13-modelo-130-pagos-fraccionados-carry-P01-S03` - add a selector unit test asserting the expanding-span mode emits the correct anchor set per target (1T empty, 2T={1T}, 3T={1T,2T}, 4T={1T,2T,3T}) and that the collision gate plus _is_direct_previous_filing_binding classify it as a direct previous_filing binding, computing expected anchors by an independent enumeration not the selector method under test
- `2026-06-13-modelo-130-pagos-fraccionados-carry-P02-S04` - check git status for peer WIP on the M130 registry, then flip casilla 05 from input_kind manual to bound and add the previous_filing span binding selecting source_modelo 130 with the new expanding-span mode, carrying raw prior casilla 07 and casilla 16 anchors with aggregation op sum
- `2026-06-13-modelo-130-pagos-fraccionados-carry-P02-S05` - author the casilla 05 registry formula computing sum of per-quarter max(0, prior 07_q) minus sum of prior 16_q (positive-part per quarter before summing, minoracion subtracted), preserving the carried prior-filing values unmodified (shape 2a)
- `2026-06-13-modelo-130-pagos-fraccionados-carry-P02-S06` - ground the casilla 05 binding and formula source_citations in the verbatim AEAT instrucciones casilla-05 definition with required_text drawn from the suma-de-las-cantidades-positivas-casilla-07-minorada-casilla-16 quote, per registry-calculation-legal-grounding
- `2026-06-13-modelo-130-pagos-fraccionados-carry-P02-S07` - confirm casilla 07 formula (07 = 04 - 05 - 06) is unchanged and now reads a populated bound casilla 05, then verify casilla 05 no longer over-states the resultado on a cumulative 2T, 3T, and 4T calculate via a registry-load behaviour assertion
- `2026-06-13-modelo-130-pagos-fraccionados-carry-P03-S08` - intersect the expanding-span candidate-quarter set with the periods for which a filing obligation actually existed, reading the operator-declared activity_start_date axis (the same field the deadline engine consumes for pre-alta suppression) so the alta-containing quarter is the first owed quarter and the span starts strictly after it, per the first-filer-attestation authority
- `2026-06-13-modelo-130-pagos-fraccionados-carry-P03-S09` - materialise casilla 05 as a clean Decimal zero with the absent-by-design provenance marker when the span is empty (true 1T, first-filer first quarter, or alta quarter), null-not-error, mirroring the casilla-15 1T path
- `2026-06-13-modelo-130-pagos-fraccionados-carry-P03-S10` - teach the observation-coverage validator to treat an empty span as satisfied (not a missing required observation) so a first filer fires no blocker, extending previous_filing_observation_requirements anchor derivation
- `2026-06-13-modelo-130-pagos-fraccionados-carry-P03-S11` - encode the casilla-16 filed-zero-vs-not-captured distinction: a prior observation carrying casilla 16 = 0 is a no-op, a prior observation lacking any casilla-16 entry lets the carry proceed but raises a non-blocking advisory naming the gap, never silently dropping the minoracion
- `2026-06-13-modelo-130-pagos-fraccionados-carry-P04-S12` - build a multi-quarter M130 fixture (prior 1T/2T/3T filings with chosen ingresos/gastos including at least one quarter whose casilla 07 is negative and at least one non-zero casilla 16), let the engine produce each prior 07 and 16, and assert the 4T casilla 05 equals sum max(0,07_q) minus sum 16_q computed from the AEAT instrucciones rule via an independent helper, a different code path than the span binding under test, per no-tautological-calculation-tests
- `2026-06-13-modelo-130-pagos-fraccionados-carry-P04-S13` - add the first-quarter-fires-nothing case: assert a 1T (and a first-filer/alta first quarter) produces casilla 05 = Decimal zero with absent-by-design provenance and emits no blocker and no prior-payment advisory
- `2026-06-13-modelo-130-pagos-fraccionados-carry-P04-S14` - add the coverage-validator-treats-empty-span-as-satisfied case: assert previous_filing_observation_requirements emits no required observation for an empty span and the cross-period gate returns clean for a genuine first filer
- `2026-06-13-modelo-130-pagos-fraccionados-carry-P04-S15` - add a parity-style regression proving the casilla-15 single-offset op=copy carry and the casilla-05 expanding-span op=sum carry both resolve correctly on a shared multi-quarter fixture, so the selector extension does not regress the modelo-130-relation-regression guarantees
- `2026-06-13-modelo-130-pagos-fraccionados-carry-P04-S16` - assert the Stage-1 prior_payment_not_deducted advisory degrades to fire only when a prior filing exists in the catalogue but its observation is unreadable/absent so the carry could not populate, and stays silent when the span binding resolves casilla 05 cleanly to non-zero

### plan

- `2026-06-13-modelo-130-pagos-fraccionados-carry-plan` - `modelo-130-pagos-fraccionados-carry` `casilla 05 cumulative pagos-fraccionados carry (target-relative same-ejercicio expanding span)` plan

### research

- `2026-06-13-modelo-130-pagos-fraccionados-carry-research` - `modelo-130-pagos-fraccionados-carry` research: investigation backing the decision
