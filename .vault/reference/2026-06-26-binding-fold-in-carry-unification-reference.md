---
tags:
  - '#reference'
  - '#binding-fold-in-carry-unification'
date: '2026-06-26'
modified: '2026-06-26'
related:
  - "[[2026-06-26-binding-fold-in-carry-unification-adr]]"
  - "[[2026-06-26-binding-fold-in-carry-unification-plan]]"
  - "[[2026-06-10-calculation-aggregation-taxonomy-adr]]"
  - "[[2026-05-19-live-iva-compensation-wallet-adr]]"
  - "[[2026-06-10-period-revision-resolution-adr]]"
---



# `binding-fold-in-carry-unification` reference: `phase-2.3 fold-in and carry anchor pins`

## Summary

This reference pins the EXACT current-state (HEAD 7cec5fa9c) anchors the phase-2.3 plan steps edit: the cross-filing fold-in value layer (two requirement records, three observation-fold loops, duplicated period-offset wrappers), the compensacion-carry surfaces, the MultiYearResolver orphan, the untyped relation aggregation op, and the conformant shapes plus carry-trust boundary that must be PRESERVED. Each anchor names the file, the line at HEAD, the current shape, the plan Step that edits it, and a preservation note. ADR-vs-HEAD drift is flagged inline and consolidated at the end.

Module(s): `aeat.domain.calculations.registry`, `aeat.application.calculations`, `aeat.application.aggregation`, `aeat.domain.iva_compensation`, `aeat.core.aggregation`.

File(s): `src/aeat/domain/calculations/registry/_relations.py`, `src/aeat/domain/calculations/registry/_bindings_previous_filing.py`, `src/aeat/domain/calculations/registry/_validate_relation_sources.py`, `src/aeat/domain/calculations/registry/_binding_aggregation.py`, `src/aeat/domain/calculations/registry/_period_offset_math.py`, `src/aeat/domain/calculations/registry/_schema_surfaces.py`, `src/aeat/application/calculations/_binding_prefill.py`, `src/aeat/application/calculations/_relation_prefill.py`, `src/aeat/application/calculations/_multi_year.py`, `src/aeat/application/calculations/_iva_wallet_reconciliation.py`, `src/aeat/application/calculations/_cross_period_clean_state.py`, `src/aeat/application/aggregation/_source_mesh.py`, `src/aeat/domain/iva_compensation/_carry_forward.py`, `src/aeat/core/aggregation.py`.

## Anchor 1 - the two requirement records to collapse (F3 / C4)

`RegistryRelationSourceRequirement` - `src/aeat/domain/calculations/registry/_relations.py:33` (re-exported through the registry `__all__` at `_relations.py:25` and `registry/__init__.py:263,532`). Strict-frozen pydantic `BaseModel`. Fields: `source_modelo`, `filing_year`, `filing_periods: tuple[Period, ...]`, `periods: tuple[str, ...]`, `source_casilla_id: CasillaId` (SINGULAR), `relation_ids: tuple[RelationId, ...]`, `target_bindings: tuple[BindingId, ...]`, `dependency_role: str`, `dependency_treatment: str`, `aggregation_op: str`. Produced by `relation_source_requirements` (`_relations.py:56`). Consumed in `_relation_prefill.py` (line 45 import, lines 224/253 scoping, lines 431/450 fold) and `_cross_period_clean_state.py:26,914`.

`RegistryModeloObservationRequirement` - `src/aeat/domain/calculations/registry/_bindings_previous_filing.py:35` (re-exported through `_bindings.py:16,129` and `registry/__init__.py:53,530`). Strict-frozen pydantic `BaseModel`. Fields: `modelo`, `filing_period: Period | None`, `filing_year`, `period: str` (SINGULAR), `binding_ids: tuple[BindingId, ...]`, `source_casilla_ids: tuple[CasillaId, ...]` (PLURAL). Produced by `previous_filing_observation_requirements` (`_bindings_previous_filing.py:69`). Consumed in `_binding_prefill.py` (lines 349, 399, 545 walks) and `_cross_period_clean_state.py:25,897`.

Near-identical, NOT field-identical. Shared spine: source modelo plus filing year plus period(s) plus binding/relation ids plus source casilla id(s). Divergences the one record must absorb: relation carries `relation_ids` / `target_bindings` / `dependency_role` / `dependency_treatment` / `aggregation_op` and a singular `source_casilla_id`; observation carries `binding_ids` and a plural `source_casilla_ids` with a singular `period`. The collapse must keep BOTH consumer sets (the relation fold AND the previous_filing walk) and the two clean-state gate consumers (`_cross_period_clean_state.py:897,914`).

Plan Step: P02.S05 (`relocation:RegistryFoldRequirement`, atomic with consumers plus top-level `__all__`). Preservation: both produced-record shapes feed live calc; one model must serve the relation fold, the previous_filing walk, and the two clean-state consumers without a field drop.

## Anchor 2 - the three near-identical observation-folding loops

Loop A (relation fold, application) - `src/aeat/application/calculations/_relation_prefill.py:431` (`_resolve_requirement_value`, the copy/sum fold over `RegistryRelationSourceRequirement`) with its per-period match helper `_observed_requirement_values` (`_relation_prefill.py:450`). Reached through the live entry point `resolve_relations_from_local_store` (`_relation_prefill.py:278`).

Loop B (relation fold, domain) - `src/aeat/domain/calculations/registry/_relations.py:299` (`_observed_requirement_values`, a BYTE-FOR-BYTE near-twin of the Loop A helper) feeding `resolve_relation_values_from_observations` (`_relations.py:181`) and the copy/sum branch in `resolve_relation_values` (`_relations.py:163-177`).

Loop C (previous_filing fold) - `src/aeat/domain/calculations/registry/_bindings_previous_filing.py:470` (`_aggregate_previous_filing_binding`: sum / copy / prior_pagos_fraccionados over a flat `values` list), reached through `resolve_previous_filing_binding_values` and the `_binding_prefill.py:330` `_gather_observations` walk plus `resolve_bindings_from_local_store` (`_binding_prefill.py:623`).

Plan Steps: P02.S06 (collapse onto the one phase-2.2 fold helper, in `_relation_prefill.py`), P02.S07 (route the previous_filing path through the one helper, in `_binding_prefill.py`). Preservation: Loop C carries the prior_pagos_fraccionados M130 casilla-05 identity (`_aggregate_prior_pagos_fraccionados`, `_bindings_previous_filing.py:488`) - a positive-part per-quarter plus minoracion subtraction that is NOT a plain sum/copy; the one helper must still produce it.

DRIFT (flag for adjudication): the ADR/plan enumerate the three loops as relation, relation-prefill, previous_filing and cite a third loop at registry `_bindings.py:~394`. There is NO fold loop in `_bindings.py` at HEAD; `_bindings.py` only RE-EXPORTS `RegistryModeloObservationRequirement` (lines 16,129). The actual three folds are Loop A (`_relation_prefill.py:431`), Loop B (`_relations.py:299`), and Loop C (`_bindings_previous_filing.py:470`). The relation half is itself DOUBLED (A application-side and B domain-side), so three near-identical loops is really two relation twins plus one previous_filing aggregator. `_binding_prefill.py:~349` is a GATHER walk (`_gather_observations`), not a value fold.

## Anchor 3 - the duplicated period-offset math

Canonical primitive: `apply_period_offset` - `src/aeat/domain/calculations/registry/_period_offset_math.py:21` (quarterly 1T..4T, pago-fraccionado 1P..3P, monthly 01..12). Already shared - NOT duplicated.

Wrapper twin 1 (relations) - `src/aeat/domain/calculations/registry/_relations.py:279` (`_derive_offset_source_anchor`) plus its `_derive_offset_source_period` (`_relations.py:274`), both wrapping `apply_period_offset` and re-raising a relation-scoped `RegistryValidationError`.

Wrapper twin 2 (previous_filing) - `src/aeat/domain/calculations/registry/_bindings_previous_filing.py:438` (`_derive_offset_source_anchor`, the same try/except wrapper with a previous-filing-scoped message). Plus the per-anchor expansion `_PreviousModeloSelector.required_period_anchors_for_target` (`_bindings_previous_filing.py:280`) and the M130 expanding-span enumerator `_prior_quarter_expanding_span_anchors` (`_bindings_previous_filing.py:451`).

Offset/year arithmetic re-derived at the application layer: `_binding_prefill.py:681` (`snapshot.filing_year + _selector_year_delta(...)`) and `_relation_prefill.py:347-352` (`snapshot.filing_year + int(filing_year_delta)`).

Plan Step: P02.S05/S06 (the one period-offset implementation rides the one requirement record). Preservation: the M130 expanding-span (1T to empty, 4T to 1T,2T,3T) and the `source_period_offset_from_target` quarterly/instalment/monthly coverage must survive; the two wrappers differ ONLY in their error-message prefix.

## Anchor 4 - the carry paths to reconcile onto the wallet authority (C3)

The M303 compensacion value (binding id `modelo-303-compensacion-pendiente-anteriores`) is sourced from FOUR live surfaces today:

Surface 1 - Wallet decision resolver: `src/aeat/application/calculations/_iva_wallet_reconciliation.py:61` (`IvaWalletDecisionSourceResolver`, `resolver_id = "iva_wallet_decision"`, binding id pinned at line 66) and the orchestration `reconcile_modelo_303_iva_compensation` (line 104). This is the foundational AUTHORITY the ADR anchors carry on.

Surface 2 - Registry previous_filing prefill: `src/aeat/application/calculations/_binding_prefill.py:80` (`_MODELO_303_IVA_COMPENSATION_BINDING_ID`), resolved by `resolve_bindings_from_local_store` and surfaced through `extract_modelo_303_local_iva_compensation_recurrence` (`_binding_prefill.py:719`, the local-recurrence reconstruction at lines 758-771). The back-door observation-injection the ADR removes is the IVA-history merge in `_gather_single_key_observation` (`_binding_prefill.py:315-326`) feeding `_observation_from_iva_compensation_history` (`_binding_prefill.py:409`).

Surface 3 - `derive_303_compensation_available`: `src/aeat/domain/iva_compensation/_carry_forward.py:121` (posterior plus generated, generated zeroed when `refunded`). Live callers: `application/live/_filed_observation_persistence.py:582` and `adapters/outbound/aeat/sede/_declarations_observations.py:569`. The refunded-period zeroing (`m303-carry-reconciliation`) lives in the `refunded` branch here.

Surface 4 - M390 box 97/662 FIFO partition: `derive_iva_compensation_year_end_carry_partition` at `src/aeat/domain/iva_compensation/_carry_forward.py:270`. Live callers: `_relation_prefill.py:638` (the `_fifo_compensation_carry_binding_values` override at `_relation_prefill.py:613`, gated by `_compensation_carry_binding_ids` at line 589 which itself inline-re-parses the relation op at `_relation_prefill.py:605`) and `_iva_compensation_history.py:366`. Both partition the same FIFO projection (`build_iva_compensation_carry_forward_report`, `_carry_forward.py:148`).

Plan Steps: P03.S11 (`_iva_wallet_reconciliation.py` - feed/defer to wallet, remove the back-door injection), P03.S12 (`_carry_forward.py` derive_303 path onto the one authority so the M390 partition derives from the one projection). Preservation: the #1 refunded-period zero-carry, #7 box-97 prior-pending, and #12 box-662 applied-credit results (P03.S10 baseline / P03.S13 after) must not shift.

## Anchor 5 - the MultiYearResolver orphan plus the co-located live concerns

`MultiYearResolver` - `src/aeat/application/calculations/_multi_year.py:401`. CONFIRMED ORPHAN: zero live (non-test) callers. Non-test references are only its own definition, the `__init__.py` re-export (`application/calculations/__init__.py:63,115`), and its functional wrapper `resolve_prior_year_observations` (`_multi_year.py:545`, body at line 560) - which itself has ZERO references anywhere (test or non-test) at HEAD. Its docstring (`_multi_year.py:409-439`) already self-declares no live production caller. Request/report models: `MultiYearResolutionRequest` (`_multi_year.py:363`), `MultiYearResolutionReport` (`_multi_year.py:382`). Test-only consumers: `tests/test_revision_stamp_roundtrip.py:41,410,441`, `tests/test_multi_year.py`, and the KNOWN-non-enrolled inventory entry `application/aggregation/tests/test_source_resolver_enrollment.py:75`.

Co-located LIVE concerns in the SAME module file the deletion must cleanly separate from: `EnrollmentRecorder` (`_multi_year.py:184`) plus `EnrollmentEvidence` (line 139) plus `EnrollmentYearObservation` (line 93) plus `EnrollmentEvidenceError` (line 79) plus `assert_enrollment_matches_manifest` (line 317) - heavily live (M100/M130 multiyear-renta enrollment). AND `PreviousFilingSourceResolver` (`_multi_year.py:482`, `resolver_id = "previous_filing"`, `owned_sources = (BindingSourceKind.PREVIOUS_FILING,)`) - the LIVE source-mesh resolver for the previous_filing calc path; delegates to `resolve_bindings_from_local_store`.

Plan Steps: P04.S15 (grep-confirm zero callers), P04.S16 (`relocation:MultiYearResolver-removal`, separate from `EnrollmentRecorder`), P04.S17 (assert `EnrollmentRecorder` intact and importable).

DRIFT (flag for adjudication): the plan P04.S16 names ONLY `EnrollmentRecorder` as the live neighbour to separate from. The module ALSO co-locates `PreviousFilingSourceResolver` (line 482) and the dangling `resolve_prior_year_observations` (line 545). The deletion must separate the orphan from BOTH live `EnrollmentRecorder` AND `PreviousFilingSourceResolver`, and should also remove the now-fully-dangling `resolve_prior_year_observations` wrapper (it has zero references at HEAD, so it is dead weight that exists only to call the deleted orphan). Update the `__all__` baseline (`_multi_year.py:570-580`) and the package `__all__` (`application/calculations/__init__.py:63,115`) accordingly.

## Anchor 6 - the untyped relation aggregation op (F4)

`RelationDefinition.aggregation` - `src/aeat/domain/calculations/registry/_schema_surfaces.py:489` (`Mapping[str, str | int | DecimalValue | bool] | None = None`), re-exported through `_schema.py` and consumed by `_relations.py:22`. The three inline `str(...).get("op")` re-parse sites: `src/aeat/domain/calculations/registry/_relations.py:103` (requirement-keying, default copy), `src/aeat/domain/calculations/registry/_relations.py:167` (`resolve_relation_values` resolve, default copy), and `src/aeat/application/calculations/_relation_prefill.py:605` (`_compensation_carry_binding_ids` M390 partition discriminator, default empty string). Plus a fourth read at the validator: `src/aeat/domain/calculations/registry/_validate_relation_sources.py:84` (`aggregation.get("op")`, validating against the set copy/sum).

The typed op to adopt (phase-2.1): `BindingAggregation` plus `BindingAggregationOp` at `src/aeat/core/aggregation.py:50` (model) and line 18 (enum), and the single accessor `binding_aggregation_op` at `src/aeat/domain/calculations/registry/_binding_aggregation.py:43` (with the per-family default in `default_binding_aggregation_op`, line 30).

Plan Steps: P01.S01 (type the field plus hydrate at loader boundary - NOTE the field actually lives in `_schema_surfaces.py:489`, see drift D2), P01.S02 (replace the inline re-parses with the accessor), P01.S03 (enforce at registry-build in `_validate_relation_sources.py`).

DRIFT (flag for adjudication): part a - the plan P01.S01 names `_relations.py` as the file holding `RelationDefinition.aggregation`; the field is actually declared in `_schema_surfaces.py:489` (`_relations.py` only IMPORTS `RelationDefinition` from `_schema`). The typing edit lands in `_schema_surfaces.py`. Part b - `BindingAggregationOp` (`core/aggregation.py:18`) carries members SUM / ROWS / COPY / COUNT_DISTINCT / PRIOR_PAGOS_FRACCIONADOS; its docstring EXPLICITLY scopes relation copy/sum OUT (relation aggregation is described as a separate, unrelated axis not modelled there). Relations only ever use copy/sum. Adopting `binding_aggregation_op` for relations requires either reconciling that docstring exclusion or confirming relations reuse only the COPY/SUM members; note `binding_aggregation_op` currently takes a `DataBindingDefinition`, not a `RelationDefinition`, so a relation-typed accessor or a shared op-coercion path is needed.

## Anchor 7 - conformant shapes that must be PRESERVED

M130 direct previous_filing carry - the prior_pagos_fraccionados aggregation (`_aggregate_prior_pagos_fraccionados`, `_bindings_previous_filing.py:488`; op member `BindingAggregationOp.PRIOR_PAGOS_FRACCIONADOS`, `core/aggregation.py:47`; build-time invariant `_validate_previous_filing_invariants`, `_bindings_previous_filing.py:372`; optional minoracion `_optional_source_casilla_ids`, `_bindings_previous_filing.py:105`). The one helper must still produce the casilla-05 positive-part-minus-minoracion identity.

M353 per_grupo_member fan-in - `_gather_grouped_member_observations` (`_binding_prefill.py:244`) plus `_per_grupo_member_requirement_keys` (`_binding_prefill.py:380`, predicate `_is_per_grupo_member` at line 387). The cross-member enumeration (every member filing for one modelo/filing_year/period) is the missing grouping axis of the relation schema; preserve the fan-in gather plus sum-across-members shape exactly.

M303 iva-wallet carve-out plus collision gate - `_IVA_WALLET_OWNED_RELATION_TARGET_BINDINGS` (`_validate_relation_sources.py:42`, a frozenset containing only `modelo-303-compensacion-pendiente-anteriores`) and the two-gate `validate_slot_source_hygiene` / `_validate_slot_binding_source` (`_validate_relation_sources.py:183` and line 228). Gate a: a previous_filing binding must carry a DIRECT selector (`_is_direct_previous_filing_binding`, `_bindings_previous_filing.py:421`). Gate b: no binding both relation-targeted AND previous_filing-sourced, EXCEPT the wallet-owned carve-out. The dedup must keep the carve-out firing EXACTLY ONCE (no double-fire).

Plan Steps: P02.S08 (M130/M353 byte-identical after the collapse), P02.S09 (carve-out plus collision gate single-fire). Preservation: these are the conformant worked examples the one helper must reproduce, not refactor away.

## Anchor 8 - the carry-TRUST layer NOT to reopen (foundational boundary)

`revision_carry_outcome` - imported into the clean-state gate at `src/aeat/application/calculations/_cross_period_clean_state.py:46` (from `_revision_carry_gate`), consumed at `_cross_period_clean_state.py:990` where a divergent stamp becomes `CrossPeriodCleanStateBlocker.REGISTRY_REVISION_DIVERGENCE` (line 120, blocking at line 997). This is the R2 stamped-revision re-confirmation gate (period-revision-resolution-adr, carried-observations-stamp-their-revision). Phase 2.3 unifies the VALUE layer BENEATH this trust layer and does NOT edit it. The same R2 skip lives in the orphaned `MultiYearResolver` (`_multi_year.py:467`, `_revision_prefill_divergence`) - deleting the orphan removes that copy, which is correct (the live carry path R2 confirmation is the clean-state gate, not the orphan).

Preservation: no plan Step edits `_cross_period_clean_state.py` or `_revision_carry_gate.py`; they are the foundational boundary. Any change that touches the carry value must leave the R2 gate blocker/advisory behaviour byte-identical.

## Phase-2.2 settled home (where the one fold helper lands)

The phase-2.2 resolver contract is COMPLETE at HEAD: `CalculationSourceResolution` (`src/aeat/application/aggregation/_source_mesh.py:200`), `merge_source_resolutions` (`_source_mesh.py:366`), `merge_source_resolutions_by_precedence` (`_source_mesh.py:435`), and the disposition registry `build_binding_source_dispositions` (`_source_mesh.py:103`). The one fold helper P02.S06 introduces lives in or beside this contract.

## ADR-vs-HEAD drift summary (for coordinator adjudication)

D1 (Anchor 2): the ADR/plan third fold loop at registry `_bindings.py:~394` does NOT exist; that file only re-exports the requirement record. The real three folds are `_relation_prefill.py:431` (Loop A), `_relations.py:299` (Loop B, a twin of A), and `_bindings_previous_filing.py:470` (Loop C). The relation half is doubled (application plus domain), so the dedup target is two relation twins plus one previous_filing aggregator, not three distinct mechanisms. `_binding_prefill.py:~349` is a gather walk, not a fold.

D2 (Anchor 6): `RelationDefinition.aggregation` lives in `_schema_surfaces.py:489`, NOT `_relations.py` as P01.S01 states (`_relations.py` only imports `RelationDefinition`). The typing edit lands in `_schema_surfaces.py`.

D3 (Anchor 6): the `BindingAggregationOp` docstring explicitly EXCLUDES relation copy/sum as a separate, unrelated axis; `binding_aggregation_op` takes a `DataBindingDefinition`, not a `RelationDefinition`. Extending the typed op to relations needs either an enum-scope widening or a relation-specific accessor - the accessor is not drop-in reusable as-is.

D4 (Anchor 5): the orphan module co-locates `PreviousFilingSourceResolver` (live, line 482) in addition to `EnrollmentRecorder`; P04.S16 names only `EnrollmentRecorder`. The deletion must separate from BOTH, and should also remove the fully-dangling `resolve_prior_year_observations` wrapper (line 545, zero references at HEAD).

No drift on Anchors 1, 3, 4, 7, 8 - their HEAD shapes match the ADR assumptions.
