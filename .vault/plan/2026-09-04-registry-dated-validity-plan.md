---
tags:
  - '#plan'
  - '#registry-dated-validity'
date: '2026-09-04'
tier: L2
related:
  - '[[2026-09-04-registry-dated-validity-event-date-keyed-parameters-adr]]'
  - '[[2026-09-04-registry-dated-validity-regulatory-constant-placement-sweep-audit]]'
modified: '2026-09-04'
body_schema: body-v2
body_hash: 'sha256:d8461475c00fa475dde1000ce90ffc051cffa9ad1bec6ffebcd7046abc3c743e'
---

<!-- RETIRED: S01 -->

# `registry-dated-validity` plan

## Description

## Steps

### Phase `P01` - citation checked against the span its carrier defends

Adjudication rejected adding a superseded-reach field to the legal reference: a repealed provision cannot state which later revisions may cite it, so the assertion is unverifiable and its correct value would change whenever a modelo gains a revision. The mis-statement is in the CHECK. Apply the second axis the accepted evidence-window ADR already ships for deadline windows to the parameter carrier, gated on containment, a closed value window, and carrier exclusivity so the gate keeps biting.

- [x] `P01.S02` - Map every parameter-carried legal reference to the dated-value windows that parameter declares, as the legal-side twin of the shipped deadline-window source spans, and lift parameters out of the flat record walk behind an include_parameters keyword so carrier exclusivity can be tested; `src/cadrumo/domain/calculations/registry/_snapshot_internals.py`.
- [x] `P01.S03` - Admit a substantive-law citation disjoint from the revision window only when its carrying parameter declares a value whose CLOSED window is CONTAINED in the governed span, the reference is carried exclusively by parameters, and the value's axis is not submission_date; prove by detector test that an open-ended window, a non-contained window, a non-exclusive carrier and a current-era value grounded in repealed wording are each still refused; `src/cadrumo/domain/calculations/registry/_snapshot_internals.py, src/cadrumo/domain/calculations/registry/tests/`.

### Phase `P02` - operator as registry data and single-axis parameters

The prorrata pair differs by comparison operator as well as value, so without an operator field it cannot be two dated values and the Python year branch survives. Add the operator defaulting to current exclusive semantics, and refuse mixed-axis parameters at load because resolution needs every value's axis in the caller's date context and the overlap validator cannot see a cross-axis double match.

- [x] `P02.S04` - Add an explicit comparison-operator field to the dated value, defaulting to the current exclusive semantics so no existing value changes meaning, and prove the default leaves all 359 shipped values resolving identically; `src/cadrumo/domain/calculations/registry/schema_formula.py, src/cadrumo/domain/calculations/registry/tests/`.
- [x] `P02.S05` - Refuse a mixed-axis parameter at load time, because resolution requires every value's axis in the caller's date context and the overlap validator groups by axis so a cross-axis double match would otherwise surface only at runtime; `src/cadrumo/domain/calculations/registry/_validate_parameter_temporal.py, src/cadrumo/domain/calculations/registry/tests/`.

### Phase `P03` - consumer prerequisites and authoring

Thread the event date into the consumers that cannot resolve without it, then author the blocked clusters as new single-axis parameters. The bienes de inversion values are reached through zero-argument enum properties; the prorrata predicate is a pure domain function with no registry dependency, so its routing is an application-boundary decision.

- [x] `P03.S06` - Thread the acquisition date into the bienes de inversion window and divisor lookups, which are today zero-argument enum properties, keeping the enum as the classifier and moving the value resolution to a function that takes the date; `src/cadrumo/domain/bienes_inversion/register.py, src/cadrumo/domain/bienes_inversion/tests/`.
- [x] `P03.S13` - Resolve the live scaffold S06 left behind: the kind enum's window and divisor methods take an acquisition_year they immediately discard, which is a parameter with no consumer standing in production code. It is consumed by the bundle rewiring or reverted, and must not be left as-is either way; `src/cadrumo/domain/bienes_inversion/register.py, src/cadrumo/domain/bienes_inversion/tests/`.
- [ ] `P03.S10` - Add the domain parameter bundle and its resolver, rewire the bienes de inversion and prorrata calculators to take it, revert the kind enum to a pure classifier, and harden the producer-snapshot oracle to refuse a result whose carried provenance disagrees with the bundle it was handed; `src/cadrumo/domain/bienes_inversion/regularizacion_parameters.py, src/cadrumo/domain/bienes_inversion/register.py, src/cadrumo/application/calculations/bienes_inversion_regularizacion.py, src/cadrumo/application/filing/producer_snapshot.py`.
- [ ] `P03.S11` - Gate the modelo 100 revision-id coincidence: assert every filing year that modelo supports is a declared revision id, so the three existing domain parameter reads fail loudly at test time if it ever splits mid-year rather than surfacing a resolution error to an operator; `src/cadrumo/domain/calculations/registry/tests/`.
- [ ] `P03.S07` - Author the bienes de inversion windows, threshold and divisors as FILING-PERIOD parameters across all six modelo 303 and five modelo 390 revisions, grounded in the per-article corpus files that already ship, and add the tripwire gate refusing a SECOND dated value on them so the day a figure moves the work routes to the deferred acquisition axis instead of silently applying new law to an old good; `src/cadrumo/_data/registry/aeat/modelos/303/revisions/, src/cadrumo/_data/registry/aeat/modelos/390/revisions/, src/cadrumo/domain/calculations/registry/_validate_parameter_temporal.py`.
- [ ] `P03.S08` - Author the single 2015-onward prorrata especial margin as a filing-period parameter with comparison inclusive across the six modelo 303 revisions, and make the pre-2015 branch an explicit refusal naming the ejercicio and the absent parameter rather than a hardcoded constant, since no revision covers a pre-2015 filing year and no repealed-redaction reference exists to cite; `src/cadrumo/_data/registry/aeat/modelos/303/revisions/, src/cadrumo/domain/iva/prorrata.py`.
- [ ] `P03.S12` - Add the declared-reason gate the event-date ADR's own constraints require but which was never planned: admission to a non-filing axis must name the provision and the axis and be enumerable in both directions, landing as the precondition before any future parameter uses one; `src/cadrumo/domain/calculations/registry/_validate_parameter_temporal.py, src/cadrumo/domain/calculations/registry/tests/`.
- [ ] `P03.S09` - Dispatch a fresh-context reviewer over the landed change to verify no legal claim was fabricated, the retroactive guard still refuses forward values, and every shipped parameter still resolves, then implement its findings; `.vault/audit/`.

## Parallelization

## Verification
