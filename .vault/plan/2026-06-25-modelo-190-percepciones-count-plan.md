---
tags:
  - '#plan'
  - '#modelo-190-percepciones-count'
date: '2026-06-25'
modified: '2026-06-25'
tier: L2
related:
  - '[[2026-06-25-modelo-190-percepciones-count-adr]]'
---








# `modelo-190-percepciones-count` plan

### Phase `P01` - Producer-clave precondition

Prove the pull/import path supplies clave on every WithholdingObservation row so the distinct-(perceptor,clave) count cannot mis-count over a partially clave-less producer.



- [ ] `P01.S01` - Verify the pull and import path populates clave on every WithholdingObservation row; `src/aeat/application/aggregation`.
- [ ] `P01.S02` - Add a producer-clave gate test refusing a clave-less withholding row; `src/aeat/application/aggregation/tests`.

### Phase `P02` - Distinct-(perceptor,clave) count primitive

Add a distinct (perceptor_tax_id, clave, subclave) count aggregation over the existing withholding detail, grounded against the Diseno registros tipo 2.

- [ ] `P02.S03` - Add a distinct (perceptor, clave, subclave) count aggregation over the withholding source; `src/aeat/domain/calculations/registry/_withholding_bindings.py`.
- [ ] `P02.S04` - Add grounded distinct-count tests where recurring quarters count once and two claves count twice; `src/aeat/domain/calculations/registry/tests`.

### Phase `P03` - Mesh enrollment (SWEEP-GATED)

Enroll the withholding-count source on the live calc mesh so the M190 count is computed, not silently blank; executes post casilla-id sweep.

- [ ] `P03.S05` - Enroll the withholding-count source in merge_source_resolutions and the owned-source set; `src/aeat/application/modelo/_calculation_actions.py`.
- [ ] `P03.S06` - Update the resolver enrollment catalogue for the withholding-count source; `src/aeat/application/aggregation/tests/test_source_resolver_enrollment.py`.

### Phase `P04` - M190 registry re-point (SWEEP-GATED)

Re-point M190 decl.total-percepciones to the count binding and retire the nine op=sum percepciones relations; executes post casilla-id sweep.

- [ ] `P04.S07` - Re-point M190 decl.total-percepciones to the count binding; `src/aeat/_data/registry/aeat/modelos/190/revisions/2024-y-siguientes`.
- [ ] `P04.S08` - Retire the nine op=sum percepciones relations and drop their dependency entries; `src/aeat/_data/registry/aeat/modelos/190/revisions/2024-y-siguientes`.

### Phase `P05` - Gates

Pull==calculate parity and distinct-count regression grounded in the Diseno, plus the full registry and aggregation suites green.

- [ ] `P05.S09` - Add the pull equals calculate percepciones-count parity test; `src/aeat/application/calculations/tests`.
- [ ] `P05.S10` - Add the distinct-count regression and run the full registry and aggregation suites; `src/aeat/application/aggregation/tests`.

## Description

Fix Modelo 190 `decl.total-percepciones` to be the distinct count of (perceptor
NIF, clave, subclave) records ("número de registros de tipo 2", per the bundled
AEAT Diseño), replacing the current over-declaring sum of quarterly Modelo 111
perceptor counts across nine claves. The fix counts over the EXISTING clave-bearing
withholding detail (`WithholdingObservation` already carries clave/subclave +
`per_perceptor_clave` grouping) and enrols that count on the calc mesh (the
withholding source is deferred today). It does NOT touch the RET-1
`retenciones_aggregation` source (distinct-NIF, correct for M180/M193's "número de
perceptores" but an under-count for M190's percepciones). Sub-decision: ship on the
existing 2-char clave string; the `core` `RetencionClave` StrEnum is the separate
hardening (#29). Grounded by the accepted ADR + research in `related:`.

EXECUTION GATING: P03 (mesh enrollment) and P04 (M190 registry re-point) touch the
live casilla-id-sweep surface (`_calculation_actions.py` / withholding bindings /
the M190 registry), so they JOIN #6 P03 in the post-sweep execution queue and MUST
NOT run against the dirty tree. P01 (producer-clave precondition) and P02 (the count
primitive + tests) are greenfield-ish and can land earlier on clean files.

## Steps







## Parallelization

P01 and P02 are independent and may land in either order on clean files. P03 (mesh
enrollment) depends on P02 (the count primitive must exist before it is enrolled).
P04 (registry re-point) depends on P03 (the source must be live before the binding
re-points, else the box goes inert / silent-blank per no-dormant-source). P05
(gates) is last. Hard ordering: P02 -> P03 -> P04 -> P05; P01 is a precondition for
P05's correctness but parallel to P02/P03 build-wise. P03 + P04 are SWEEP-GATED
(post casilla-id sweep), executed alongside #6 P03.

## Verification

The plan succeeds when: (1) a producer-clave gate proves the pull/import path
populates `clave` on EVERY `WithholdingObservation` row (a clave-less row is
refused, not silently counted); (2) the distinct-(perceptor,clave,subclave) count
primitive returns the correct count on a constructed fixture where a perceptor
recurs across quarters under one clave (counts once) and appears under two claves
(counts twice), with expected values grounded in the Diseño, not the relation
formula; (3) the withholding-count source is enrolled in `merge_source_resolutions`
+ `_BUCKET_AGGREGATION_OWNED_SOURCES` (no-dormant-source) and the
`test_source_resolver_enrollment` catalogue gate is green; (4) M190
`decl.total-percepciones` resolves from the count binding, the nine op=sum
percepciones relations + their dependency entries are retired (no registry!=runtime
drift), and the monetary `decl.percepciones-total` relations are unchanged; (5) a
pull==calculate percepciones-count parity test passes. Every Step closed and the
full registry + aggregation suites green.
