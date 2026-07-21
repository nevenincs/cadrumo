---
tags:
  - '#plan'
  - '#retenciones-perceptor-count'
date: '2026-06-24'
modified: '2026-06-30'
tier: L2
related:
  - '[[2026-06-24-retenciones-perceptor-count-adr]]'
  - '[[2026-06-30-retenciones-perceptor-count-research]]'
---

# `retenciones-perceptor-count` plan

### Phase `P01` - Dedicated per-perceptor retención-observation store

Create the persisted distinct-NIF perceptor source the calc path lacks: a typed, encrypted, bucket-scoped retención-observation store populated from the same inputs the pull path uses.

- [x] `P01.S01` - Define the typed per-perceptor retención-observation record (perceptor NIF + scheme + percibido/retencion + modelo + period), pydantic-strict; `src/aeat/application/aggregation`.
- [x] `P01.S02` - Persist records in a bucket-scoped encrypted secure-object namespace via SecureObjectRepository, populated from the same input path that feeds the pull aggregate_per_modelo observations; `src/aeat/application/aggregation`.
- [x] `P01.S03` - Add a strict save-load-equality roundtrip + anti-tautology proof for the store, every defaultable field populated non-default; `src/aeat/application/aggregation/tests`.

### Phase `P02` - Calc-mesh distinct-perceptor source resolver + enrollment

Add a calc-mesh resolver that aggregates the store into a distinct perceptor count and materialises the perceptor-count binding, enrolled so no source is dormant.

- [x] `P02.S04` - Add a BindingSourceKind member for the new source plus the registry-vs-enum parity gate entry; `src/aeat/core`.
- [x] `P02.S05` - Add a calc-mesh ModeloSourceResolver reading the per-perceptor store and materialising the perceptor-count binding via aggregate_retenciones_180 distinct-NIF total_perceptors; `src/aeat/application/aggregation/_modelo_bindings.py`.
- [x] `P02.S06` - Enroll the resolver in merge_source_resolutions and add the source kind to _BUCKET_AGGREGATION_OWNED_SOURCES so no source is dormant; `src/aeat/application/modelo/_calculation_actions.py`.

### Phase `P03` - M180/M193 cutover + M190 percepciones split

Retire the M115-sum count relation, re-point M180 and M193 distinct-NIF counts onto the retenciones source, and preserve M190 on its distinct-percepciones withholding source. Lock the split with pull==calculate parity and grounded distinct-count tests.

- [x] `P03.S07` - Retire the M180 perceptores op=sum relation in both revisions, re-point modelo-180-total-perceptores at the binding, re-stamp the binding source, and keep the base/retenciones monetary relations; `src/aeat/_data/registry/aeat/modelos/180`.
- [x] `P03.S08` - Close M193 perceptor_count on retenciones_aggregation and preserve M190 percepciones on the withholding source, documenting the obsolete M190 grouping as a scoped deviation; `src/aeat/_data/registry/aeat/modelos/193; src/aeat/_data/registry/aeat/modelos/190; src/aeat/application/calculations/tests`.
- [x] `P03.S09` - Add grounded tests: landlord across two quarters counts once; pull==calculate perceptor-count parity; distinct-NIF anti-tautology proof; expected from the AEAT Diseño not the formula; `src/aeat/application/calculations/tests`.

## Description

Implements the accepted ADR `2026-06-24-retenciones-perceptor-count-adr` (data-model fork ratified
2026-06-24: a DEDICATED encrypted retención-observation store, not ledger modelling). Closes the
RET-1 family-wide divergence for M180 and M193 annual perceptor counts: the calc path could sum
quarterly aggregate counts and double-count a perceptor across periods while the correct distinct-NIF
count existed only on the pull/observation channel the calc mesh could not reach. M190 was reviewed
with the same family but is a distinct-percepciones count over withholding detail, not a
distinct-NIF perceptor count. P01 builds the missing persisted retenciones source; P02 wires it into
the calc mesh via a resolver using the existing validated distinct-NIF primitive; P03 cuts M180/M193
over, preserves the M190 withholding path, and locks the split with parity tests.

## Steps

## Parallelization

Strictly sequential by phase: P02 depends on P01's store existing (the resolver reads it); P03
depends on P02's resolver+binding being enrolled (re-pointing the formula before the resolver exists
would leave the binding blank - no-dormant-source). Within P03, S07 closes M180 and S08 closes M193
while documenting the M190 withholding split; S09 follows both. P03 touches the relation/binding surface -
sequence against active M303/relation peer work (re-read HEAD, explicit pathspec), since the
`_relation_prefill.py`-adjacent files are hot.

## Verification

Complete when every step is closed. Success criteria: a landlord paid across two quarters yields M180
`decl.total-perceptores` = 1 (was 2) on the calc path; pull and calculate produce an identical
perceptor count for a shared revision (parity gate green); the M115-sum perceptores relation is gone
from both M180 revisions with no dormant/blank source (`assert_no_novel_source_kinds` +
`collect_unhandled_source_diagnostics` clean); the new store passes a strict save→load→equality
roundtrip + anti-tautology proof; M193 derives from the retenciones source; M190 derives its
percepciones count from the withholding source; expected counts stay grounded in the AEAT Diseño and
withholding record semantics, not the formula under test; the focused registry/calculation tests and
feature-local vault checks are green.
