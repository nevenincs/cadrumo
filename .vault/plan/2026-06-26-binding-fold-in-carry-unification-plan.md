---
tags:
  - '#plan'
  - '#binding-fold-in-carry-unification'
date: '2026-06-26'
modified: '2026-06-26'
tier: L2
related:
  - '[[2026-06-26-binding-fold-in-carry-unification-adr]]'
  - '[[2026-06-10-calculation-aggregation-taxonomy-adr]]'
  - '[[2026-05-19-live-iva-compensation-wallet-adr]]'
  - '[[2026-06-10-period-revision-resolution-adr]]'
  - '[[2026-06-21-m303-carry-reconciliation-adr]]'
  - '[[2026-06-21-m390-iva-carry-boxes-adr]]'
  - '[[2026-06-26-binding-resolver-contract-unification-plan]]'
---

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the
       related: field above.
     - The related: field carries the AUTHORISING documents
       (ADR, research, reference, prior plan) for every Step in
       this plan. Steps inherit this chain; per-row reference
       footers do not exist.
     - NEVER use [[wiki-links]] or markdown links in the
       document body. -->

# `binding-fold-in-carry-unification` plan

Collapse the cross-filing fold-in value layer onto one requirement record, one observation-fold helper, and one typed relation aggregation, anchor compensacion carry on the wallet authority, and delete the `MultiYearResolver` orphan, with every collapse proven behaviour-preserving against the full-calc, cross-period-continuity, and oracle suites.

### Phase `P01` - type relation aggregation (extend binding-aggregation-is-typed to relations)

Make RelationDefinition.aggregation the typed BindingAggregation plus BindingAggregationOp model and replace the three inline op re-parses with the one accessor, validated at registry-build.

- [x] `P01.S01` - vaultspec-standard-executor: type RelationDefinition.aggregation as the BindingAggregation plus BindingAggregationOp model, hydrating the registry op token at the loader boundary (report-before-land, abort-on-WIP); `src/aeat/domain/calculations/registry/_relations.py`.
- [x] `P01.S02` - vaultspec-standard-executor: replace the three inline str(relation.aggregation).get('op') re-parses with the one binding_aggregation_op accessor at the requirement-keying and resolve sites; `src/aeat/domain/calculations/registry/_relations.py`.
- [x] `P01.S03` - vaultspec-standard-executor: enforce the typed relation op at registry-build via the section validator, rejecting an unknown op at build not resolve time; `src/aeat/domain/calculations/registry/_validate_relation_sources.py`.
- [x] `P01.S04` - vaultspec-code-reviewer: VERIFICATION GATE 5a - run full-calc, cross-period-continuity, and oracle suites after the relation-op typing and assert NO casilla value shifts and binding-aggregation-is-typed conformance green; `src/aeat/domain/calculations/registry/tests/test_modelo_303_registry.py`.

### Phase `P02` - one requirement record and one observation-fold helper

Collapse the two requirement records and the three observation-folding loops onto one typed requirement model and one fold helper with one period-offset, preserving the M130 direct-carry and M353 per_grupo_member shapes and the M303 carve-out single-fire.

- [x] `P02.S05` - vaultspec-high-executor: collapse RegistryRelationSourceRequirement and RegistryModeloObservationRequirement onto one typed requirement model with one period-offset field, atomic relocation:RegistryFoldRequirement with consumers and top-level __all__ re-export; `src/aeat/domain/calculations/registry/_relations.py`.
- [x] `P02.S06` - vaultspec-high-executor: collapse the three near-identical observation-folding loops onto the one fold helper from the phase-2.2 resolver contract, preserving the M130 direct-carry and M353 per_grupo_member output shapes exactly (apply-cached on collision, peer-WIP likely); `src/aeat/application/calculations/_relation_prefill.py`.
- [x] `P02.S07` - vaultspec-high-executor: route the previous_filing observation-fold path through the one helper, removing the third duplicate loop (apply-cached on collision, peer-WIP likely); `src/aeat/application/calculations/_binding_prefill.py`.
- [x] `P02.S08` - vaultspec-code-reviewer: VERIFICATION GATE 5b - run full-calc, cross-period-continuity, and oracle suites after the fold-helper collapse and assert NO casilla value shifts with M130 and M353 shapes byte-identical; `src/aeat/application/calculations/tests/test_pull_path_calculate_path_casilla_parity.py`.
- [x] `P02.S09` - vaultspec-code-reviewer: VERIFICATION GATE 3 - assert the M303 modelo-303-compensacion-pendiente-anteriores carve-out and the relation/previous_filing collision gate still fire EXACTLY ONCE post-dedup, never a double-fire; `src/aeat/domain/calculations/registry/_validate_relation_sources.py`.

### Phase `P03` - one compensacion-carry authority anchored on the wallet

Anchor compensacion carry on the foundational iva-wallet decision and reconcile the registry previous_filing formula and derive_303 paths to feed or defer to it disposition-aware, preserving every landed carry-fix result.

- [x] `P03.S10` - vaultspec-code-reviewer: VERIFICATION GATE 1-BEFORE - run the #1 M303 refunded-period zero-carry, #7 M390 box 97 prior-pending, and #12 M390 box 662 applied-credit regression gates and record the baseline casilla values before any carry-reconciliation edit; `src/aeat/application/calculations/tests/test_modelo_303_refunded_period_carry.py`.
- [x] `P03.S11` - vaultspec-high-executor: reconcile the registry previous_filing compensacion formula path to feed or defer to the iva-wallet authority disposition-aware, removing the back-door observation-injection second route (apply-cached on collision, peer-WIP likely); `src/aeat/application/calculations/_iva_wallet_reconciliation.py`.
- [x] `P03.S12` - vaultspec-high-executor: reconcile the derive_303_compensation_available carry path onto the one wallet authority so the M390 box 97/662 FIFO partition derives from the one projection (apply-cached on collision); `src/aeat/domain/iva_compensation/_carry_forward.py`.
- [x] `P03.S13` - vaultspec-code-reviewer: VERIFICATION GATE 1-AFTER - re-run the #1 M303 refunded-period, #7 M390 box 97, and #12 M390 box 662 regression gates after each carry-reconciliation sub-step and assert ZERO casilla value shifts against the recorded baseline; `src/aeat/application/modelo/tests/test_modelo_390_fifo_carried_pending.py`.
- [x] `P03.S14` - vaultspec-code-reviewer: VERIFICATION GATE 2 - assert the #6/#28 perceptor-count and percepciones-count results in the same value layer are unchanged after the carry-authority reconciliation; `src/aeat/application/aggregation/tests/test_retenciones.py`.

### Phase `P04` - delete the MultiYearResolver orphan

Delete the confirmed-orphan MultiYearResolver after grep-confirming zero live callers, cleanly separating it from the live EnrollmentRecorder that shares its module file.

- [x] `P04.S15` - vaultspec-low-executor: VERIFICATION GATE 4 - grep-confirm ZERO live MultiYearResolver callers across src/aeat immediately before deletion, recording the grep result in the Step Record; `src/aeat/application/calculations/_multi_year.py`.
- [x] `P04.S16` - vaultspec-standard-executor: delete the MultiYearResolver class and its request/report models, cleanly separating it from the live EnrollmentRecorder in the shared module, atomic relocation:MultiYearResolver-removal with __all__ baseline; `src/aeat/application/calculations/_multi_year.py`.
- [x] `P04.S17` - vaultspec-code-reviewer: assert the live EnrollmentRecorder remains intact and importable through the top-level __all__ re-export and the full collect-only gate is clean after the orphan deletion; `src/aeat/application/calculations/tests/test_multi_year.py`.

## Description

Phase 2.3 of the bindings-architecture-unification sweep. This plan executes the four-point layering in the `binding-fold-in-carry-unification` ADR: it closes the value-layer fragmentation the `calculation-aggregation-taxonomy` ADR left standing after it assigned mechanism ownership but never removed the duplicate codepath (audit findings F3 and F4, conflicts C3 and C4).

The four points, sequenced as phases. One requirement record plus one observation-fold helper: `RegistryRelationSourceRequirement` and `RegistryModeloObservationRequirement` collapse onto one typed model, and the three near-identical observation-folding loops (relation, relation-prefill, previous_filing) onto one helper with one period-offset implementation. Type relation aggregation: `RelationDefinition.aggregation` becomes the typed `BindingAggregation` plus `BindingAggregationOp` model from phase 2.1, replacing the inline `str(...).get("op")` re-parses, extending the `binding-aggregation-is-typed` rule to the relation half it skipped. One compensacion-carry authority: the foundational `live-iva-compensation-wallet` decision is the carry authority, and the registry `previous_filing` formula path plus the `derive_303_compensation_available` path are reconciled to feed or defer to it disposition-aware, with the `m303-carry-reconciliation` and `m390-iva-carry-boxes` mechanics landing as children. Delete the `MultiYearResolver` orphan per `no-dormant-source-resolvers`, cleanly separated from the heavily-live `EnrollmentRecorder` sharing its module file.

Dependencies. This plan depends on phase 2.1 (`binding-source-kind-taxonomy-unification`, COMPLETE at HEAD: the `BindingSourceKind` authority and `BindingAggregationOp` enum landed) and on phase 2.2 (`binding-resolver-contract-unification`, IN-FLIGHT: the one fold helper lives in the phase-2.2 resolver contract). Execution sequences after both. The Option-C mechanism-ownership topology (`calculation-aggregation-taxonomy`) and the R2 carry-TRUST gate (`period-revision-resolution`) are foundational and are NOT reopened; this phase unifies the VALUE layer beneath the trust layer.

Constraints carried from the ADR. Behaviour-preserving by construction, proven not asserted: NO casilla value may shift across any collapse. The M130 direct-carry and M353 `per_grupo_member` fan-in are the conformant shapes the one helper must still produce exactly. The M303 iva-wallet carve-out (`modelo-303-compensacion-pendiente-anteriores`) and the `relation-slot-bindings-declare-relation-source` collision gate must survive the dedup and fire EXACTLY ONCE post-dedup, never a double-fire. The carry reconciliation intersects already-landed carry fixes (#1 M303 refunded-period zero-carry, #7 M390 box 97 prior-pending, #12 M390 box 662 applied-credit) and the #6/#28 perceptor/percepciones count results; all must be preserved exactly.

## Steps







## Parallelization

Phases are hard-ordered, not parallel. Phase P01 (typed relation aggregation) lands first because it is the lowest-risk, registry-build-only change that the fold-helper unification in P02 reads through the one `binding_aggregation_op` accessor. Phase P02 (one requirement record plus one fold helper) depends on P01 and on the phase-2.2 resolver contract being merged. Phase P03 (one carry authority) depends on P02 because the reconciled carry paths fold through the unified helper. Phase P04 (delete the orphan) is independent of carry but is sequenced last so the deletion runs against a settled value layer with the fewest concurrent peer edits.

Within each phase, the collapse Steps are sequential (each must leave the suite green before the next), and every verification-gate Step is a hard barrier: the phase does not advance past a red gate. The whole plan is single-threaded by correctness risk; this is not a parallelism candidate.

Shared-branch discipline binds every Step. Report-before-land and abort-on-WIP (check `git diff -- <file>` and `git log -1 -- <file>` at HEAD immediately before editing; peer campaigns codex and r2 land here in parallel). The Steps touching `_calculation_actions.py`, `_binding_prefill.py`, and `_relation_prefill.py` are flagged apply-cached: stage a HEAD-anchored own-edits-only patch to the index, verify zero foreign markers, then commit, rather than waiting on or discarding peer WIP. Relocations are atomic single-symbol commits tagged `relocation:<symbol>` with every consumer, fixture, and `__all__` baseline in one index; cross-package symbols are consumed only through top-level `__all__` re-exports.

## Verification

The plan is complete when every Step is closed (`- [x]`) and the five coordinator verification gates have each passed with the asserted invariant.

Gate 1 (P03.S10 before, P03.S13 after - carry-authority regression intersection): the #1 M303 refunded-period zero-carry, #7 M390 box 97 prior-pending, and #12 M390 box 662 applied-credit regression gates are run BEFORE the carry-reconciliation edits (S10 records the baseline) and re-run AFTER each carry-reconciliation sub-step (S13), asserting ZERO casilla value shifts. Gate 2 (P03.S14 - perceptor/percepciones preservation): the #6/#28 perceptor-count and percepciones-count results in the same value layer assert unchanged. Gate 3 (P02.S09 - carve-out single-fire): the M303 iva-wallet carve-out and the relation/`previous_filing` collision gate fire EXACTLY ONCE post-dedup, proven by the collision-gate and M303 registry test surfaces. Gate 4 (P04.S15 - orphan deletion): a grep confirms ZERO live `MultiYearResolver` callers immediately before deletion (S15), and the live `EnrollmentRecorder` in the shared module is verified intact and importable (S17). Gate 5 (P01.S04 and P02.S08 - no-shift after each collapse): the full-calc, cross-period-continuity, and oracle suites are green after EACH collapse, with NO casilla value shifts.

Standing criteria across all Steps: every registry-build gate, the `binding-aggregation-is-typed` conformance, the `relation-slot-bindings-declare-relation-source` collision gate, and `pytest --collect-only -q` clean collection hold at every commit; no behaviour change is asserted without a passing suite proving it.
