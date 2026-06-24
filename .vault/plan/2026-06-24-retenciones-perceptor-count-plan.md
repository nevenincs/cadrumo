---
tags:
  - '#plan'
  - '#retenciones-perceptor-count'
date: '2026-06-24'
modified: '2026-06-24'
tier: L2
related:
  - '[[2026-06-24-retenciones-perceptor-count-adr]]'
---








# `retenciones-perceptor-count` plan

### Phase `P01` - Dedicated per-perceptor retención-observation store

Create the persisted distinct-NIF perceptor source the calc path lacks: a typed, encrypted, bucket-scoped retención-observation store populated from the same inputs the pull path uses.



- [ ] `P01.S01` - Define the typed per-perceptor retención-observation record (perceptor NIF + scheme + percibido/retencion + modelo + period), pydantic-strict; `src/aeat/application/aggregation`.
- [ ] `P01.S02` - Persist records in a bucket-scoped encrypted secure-object namespace via SecureObjectRepository, populated from the same input path that feeds the pull aggregate_per_modelo observations; `src/aeat/application/aggregation`.
- [ ] `P01.S03` - Add a strict save-load-equality roundtrip + anti-tautology proof for the store, every defaultable field populated non-default; `src/aeat/application/aggregation/tests`.

### Phase `P02` - Calc-mesh distinct-perceptor source resolver + enrollment

Add a calc-mesh resolver that aggregates the store into a distinct perceptor count and materialises the perceptor-count binding, enrolled so no source is dormant.

- [ ] `P02.S04` - Add a BindingSourceKind member for the new source plus the registry-vs-enum parity gate entry; `src/aeat/core`.
- [ ] `P02.S05` - Add a calc-mesh ModeloSourceResolver reading the per-perceptor store and materialising the perceptor-count binding via aggregate_retenciones_180 distinct-NIF total_perceptors; `src/aeat/application/aggregation/_modelo_bindings.py`.
- [ ] `P02.S06` - Enroll the resolver in merge_source_resolutions and add the source kind to _BUCKET_AGGREGATION_OWNED_SOURCES so no source is dormant; `src/aeat/application/modelo/_calculation_actions.py`.

### Phase `P03` - M180/M190/M193 cutover + pull==calculate parity

Retire the M115-sum count relation and re-point the family onto the one distinct-NIF source, locked by a pull==calculate parity gate and grounded distinct-count tests.

- [ ] `P03.S07` - Retire the M180 perceptores op=sum relation in both revisions, re-point modelo-180-total-perceptores at the binding, re-stamp the binding source; `keep the base/retenciones monetary relations; `src/aeat/_data/registry/aeat/modelos/180`.
- [ ] `P03.S08` - Extend the distinct-perceptor source to the M190 and M193 perceptor_count bindings; `src/aeat/_data/registry/aeat/modelos/193`.
- [ ] `P03.S09` - Add grounded tests: landlord across two quarters counts once; pull==calculate perceptor-count parity; distinct-NIF anti-tautology proof; expected from the AEAT Diseño not the formula; `src/aeat/application/calculations/tests`.

## Description

Implements the accepted ADR `2026-06-24-retenciones-perceptor-count-adr` (data-model fork ratified
2026-06-24: a DEDICATED encrypted retención-observation store, not ledger modelling). Closes the
RET-1 family-wide divergence: the M180/M190/M193 annual perceptor count is wrong on the calc path
(sums quarterly M115 aggregate counts → double-counts a perceptor across quarters) while the correct
distinct-NIF count exists only on the pull/observation channel the calc mesh can't reach. P01 builds
the missing persisted source; P02 wires it into the calc mesh via a resolver using the existing
validated distinct-NIF primitive; P03 cuts the family over and locks pull==calculate parity.

## Steps







## Parallelization

Strictly sequential by phase: P02 depends on P01's store existing (the resolver reads it); P03
depends on P02's resolver+binding being enrolled (re-pointing the formula before the resolver exists
would leave the binding blank - no-dormant-source). Within P03, S07 (M180) and S08 (M190/M193) are
independent registry edits; S09 (tests) follows both. P03 touches the relation/binding surface —
sequence against active M303/relation peer work (re-read HEAD, explicit pathspec), since the
`_relation_prefill.py`-adjacent files are hot.

## Verification

Complete when every step is closed. Success criteria: a landlord paid across two quarters yields M180
`decl.total-perceptores` = 1 (was 2) on the calc path; pull and calculate produce an identical
perceptor count for a shared revision (parity gate green); the M115-sum perceptores relation is gone
from both M180 revisions with no dormant/blank source (`assert_no_novel_source_kinds` +
`collect_unhandled_source_diagnostics` clean); the new store passes a strict save→load→equality
roundtrip + anti-tautology proof; M190/M193 counts derive from the same source; expected counts
grounded in the AEAT Diseño (not the formula under test); full registry builds and the feature-scoped
suite + `vaultspec-core vault check` are green.

