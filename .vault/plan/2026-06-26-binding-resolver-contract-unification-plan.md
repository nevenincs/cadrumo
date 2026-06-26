---
tags:
  - '#plan'
  - '#binding-resolver-contract-unification'
date: '2026-06-26'
modified: '2026-06-26'
tier: L2
related:
  - '[[2026-06-26-binding-resolver-contract-unification-adr]]'
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

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #plan) and one feature tag.
     Replace binding-resolver-contract-unification with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     tier is mandatory for new plans. Allowed: L1, L2, L3, L4.
     L1 = Steps only. L2 = Phases above Steps. L3 = Waves above
     Phases above Steps. L4 = Epic above Waves above Phases above
     Steps; PM association required. Pre-existing plans without this
     field default to L2.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'. The related field
     carries the AUTHORIZING documents (ADR, research, reference, prior
     plan) for every Step in this plan; Steps inherit this chain;
     per-row reference footers do not exist.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->


<!-- HIERARCHY AND TIERS:
     Epic > Wave > Phase > Step. Step is the canonical leaf-row
     noun. Execution Record artifact: <Step Record>.
     Tier is declared in frontmatter as tier: L1/L2/L3/L4
     (mandatory for new plans; pre-existing plans without the
     field default to L2 and the writer adds the field on first
     edit). The tier selects containers:
       L1 = Steps only.
       L2 = Phases above Steps.
       L3 = Waves above Phases above Steps.
       L4 = Epic above Waves above Phases above Steps; MUST declare
            a project-management association in the Epic intent
            block prose.
     Selection is by complexity criteria, not container counting.
     Writer never invents containers to qualify a tier. -->

<!-- IDENTIFIERS AND ROW CONTRACT:
     S##, P##, W## are flat, per-document, append-only, immutable.
     Promotion adds containers without renumbering. Gaps are not
     reused.
     Display paths are computed from current grouping:
       Step path:    L1 S##   L2 P##.S##   L3/L4 W##.P##.S##
       Phase heading:        L2 P##       L3/L4 W##.P##
       Wave heading:                      L3/L4 W##
     Row format:
       - [ ] `<display-path>` - imperative-verb action; `path/to/file`.
     Two-state checkboxes only ([ ] open, [x] closed). No per-row
     reference footers; wiki-links and markdown links are forbidden
     in plan body. Authorizing documents go in the plan's `related:`
     frontmatter once.
     ASCII spaced hyphens everywhere; em-dash (U+2014) and en-dash
     (U+2013) are forbidden. Step rows within a Phase are
     contiguous. -->

<!-- NO COMPRESSION:
     N self-similar actions = N rows. Never collapse into "for each
     X, do Y" / "across all callers, do Z" / "in every module,
     replace W". The rule applies at every tier including L1. -->

<!-- VAULTSPEC-CORE VAULT PLAN CLI:
     The `vaultspec-core vault plan` CLI is the canonical surface for
     structural manipulation of this plan document. Writers and
     executors MUST use `vaultspec-core vault plan step add/insert/move/
     remove/check/uncheck/toggle/edit`,
     `vaultspec-core vault plan phase add/move/remove/edit`,
     `vaultspec-core vault plan wave add/move/remove/edit`,
     `vaultspec-core vault plan epic intent`, and
     `vaultspec-core vault plan tier promote/demote` for every
     identifier-affecting change rather than hand-editing the row
     grammar. Hand edits are tolerated by the parser but flagged by
     `vaultspec-core vault plan check`; canonical-identifier preservation is
     guaranteed only when the CLI performs the mutation. Run
     `vaultspec-core vault plan --help` for the full subcommand
     surface. -->

# `binding-resolver-contract-unification` plan

### Phase `P01` - One result envelope: retire the vestigial source-resolution envelopes

Make CalculationSourceResolution the single resolved-source envelope by retiring the vestigial CalculationBindingResolution, the M349-only PerModeloRegistryBindingResolution, the consumer-less ModeloLedgerBindingAggregation, and the advertised-but-bypassed CasillaAggregation canonical framing; migrate the few real consumers first.

- [x] `P01.S01` - Retire the advertised-canonical CasillaAggregation/CasillaProvenance framing from the package docstring, keeping the live ledger-aggregation classes but removing the bypassed canonical claim; `src/aeat/application/aggregation/__init__.py`.
- [x] `P01.S02` - Migrate the M349-only PerModeloRegistryBindingResolution consumer onto CalculationSourceResolution, then delete the PerModeloRegistryBindingResolution model and resolve_per_modelo_registry_binding_values in the same atomic relocation commit; `src/aeat/application/aggregation/_registry_provider.py`.
- [x] `P01.S03` - Delete the consumer-less ModeloLedgerBindingAggregation model and its test after confirming zero live consumers at HEAD; `src/aeat/application/aggregation/_modelo_bindings.py`.
- [x] `P01.S04` - Drop the deleted envelopes from the aggregation package __all__ and lazy __getattr__ re-export surface in the same commits that delete them; `src/aeat/application/aggregation/__init__.py`.

### Phase `P02` - Fold profile and borrador into the mesh, ending the B to A to B wrap

Make profile and borrador first-class mesh resolvers consumed directly through merge_source_resolutions, removing the BindingSourceResolution Protocol and the ProfileSourcedBindingResult / Modelo100BorradorBindingResult wrap and unwrap, preserving the caller-override precedence ladder and the borrador provenance trace as explicit mesh-merge precedence.

- [x] `P02.S05` - Promote the profile mesh resolver result onto CalculationSourceResolution and drop the ProfileSourcedBindingResult wrap, keeping the date-binding and provenance channels intact; `src/aeat/application/modelo/_profile_binding.py`.
- [x] `P02.S06` - Promote the borrador mesh resolver result onto CalculationSourceResolution and drop the Modelo100BorradorBindingResult wrap, preserving the borrador_snapshot_id and bindings_sourced_from_borrador provenance trace the downstream observation builder consumes; `src/aeat/application/modelo/_borrador_binding.py`.
- [x] `P02.S07` - Enroll the profile and borrador resolvers into merge_source_resolutions with explicit mesh-merge precedence preserving the declared precedence ladder, applying the apply-cached-on-collision drive against the live peer WIP; `src/aeat/application/modelo/_calculation_actions.py`.
- [x] `P02.S08` - Remove the BindingSourceResolution Protocol and the resolve_calculation_binding_inputs B-to-A-to-B wrap, re-homing the channel-mismatch and previous-filing-override helpers onto the mesh-merged resolution, applying the apply-cached-on-collision drive against the live peer WIP; `src/aeat/application/modelo/_binding_resolution.py`.
- [x] `P02.S09` - Update the calculate orchestration call site to consume the mesh-merged resolution directly instead of CalculationBindingResolution, sourcing borrador provenance from the borrador resolution, applying the apply-cached-on-collision drive against the live peer WIP; `src/aeat/application/modelo/_calculation_actions.py`.

### Phase `P03` - Adjudicate the per-modelo aggregation service (shape C)

Bring counterpart 347/349 and foreign-assets 720 onto the live calculate mesh as ModeloSourceResolvers (closing the orphan), collapse retenciones to one mesh path, and keep the CLI aggregate verb as a thin delegating projection. Because a folded source now RESOLVES rather than advisory-defers, an enrolled-but-wrong resolver under-declares silently; each fold therefore carries an explicit per-source correctness gate (347, 349, 720, and the retenciones collapse) asserting the live-mesh value equals the prior aggregation output exactly, so behaviour-preservation is proven, not asserted, with no casilla value shift.

> **SCOPE REFINEMENT (2026-06-26, coordinator-ruled - see the ADR Execution refinement on §3):** the counterpart 347/349 + foreign-assets 720 fold (Steps **S10/S11/S12** + correctness gates **S20/S21**) is SCOPED OUT of phase-2.2 to a grounded follow-up (task **#36**) - it is NOT mechanical (standalone `CounterpartObservation`s have no calculate-path source; M349 counterpart is already live via `InvoiceCatalogueSourceResolver`; shape-C counterpart/720 are CLI-reachable, NOT dormant mesh resolvers, so deferral breaches no no-dormant invariant). #36 grounds M347/M349/M720 per-modelo (already-live / genuinely-unrouted-silent-blank / shape-C-redundant) then acts per class. The **retenciones collapse (S13) + its correctness gate (S19) are KEPT** here - retenciones is already canonical (the enrolled `RetencionesAggregationSourceResolver`, #6), so collapsing the redundant shape-C `aggregate_retenciones` to it is mechanical and behaviour-preserving. `FOREIGN_ASSET` stays in `DEFERRED_SOURCE_KINDS` (S12 deferred). These deferred Steps are tracked, not dropped.

- [ ] `P03.S10` - Author a counterpart 347/349 ModeloSourceResolver returning CalculationSourceResolution that delegates to aggregate_counterpart_347/349, behaviour-preserving against the existing counterpart suites; `src/aeat/application/aggregation/_counterpart.py`.
- [ ] `P03.S11` - Author a foreign-assets 720 ModeloSourceResolver returning CalculationSourceResolution that delegates to aggregate_foreign_assets_720, behaviour-preserving against the existing 720 suites; `src/aeat/application/aggregation/_foreign_assets.py`.
- [ ] `P03.S21` - Prove the counterpart 347/349 mesh resolver produces a CORRECT aggregation value by oracle/calc-smoke check against a 347 and a 349 fixture, asserting the live-mesh resolution equals the prior aggregate_counterpart_347/349 output exactly so the now-resolving (no longer deferred) source cannot silently under-declare; `src/aeat/application/aggregation/tests/test_per_modelo_service.py`.
- [ ] `P03.S20` - Prove the foreign-assets 720 mesh resolver produces a CORRECT aggregation value by oracle/calc-smoke check against a 720 fixture, asserting the live-mesh resolution equals the prior aggregate_foreign_assets_720 output exactly so the now-resolving (no longer deferred) source cannot silently under-declare; `src/aeat/application/aggregation/tests/test_per_modelo_service.py`.
- [ ] `P03.S12` - Enroll the counterpart and foreign-assets resolvers in merge_source_resolutions and remove FOREIGN_ASSET from DEFERRED_SOURCE_KINDS now that it has a live resolver, applying the apply-cached-on-collision drive against the live peer WIP; `src/aeat/application/modelo/_calculation_actions.py`.
- [ ] `P03.S13` - Collapse the retenciones double-path so the per-modelo service retenciones branch delegates to the same mesh RetencionesAggregationSourceResolver, retiring the duplicate retenciones service result type without changing the landed perceptor-count result; `src/aeat/application/aggregation/_service.py`.
- [ ] `P03.S19` - Prove the retenciones collapse is behaviour-preserving by asserting the single mesh RetencionesAggregationSourceResolver reproduces the prior per-modelo-service aggregation value exactly against a 111/115/123/180/190/193 fixture, with the landed perceptor-count result unchanged and no casilla value shift; `src/aeat/application/aggregation/tests/test_per_modelo_service.py`.
- [ ] `P03.S14` - Keep the CLI aggregate verb as a thin delegating projection whose aggregation delegates to the ONE mesh resolver with no re-implemented aggregation in the verb and whose persist-retencion-observations side-effect delegates to the existing single-writer observation repository with no bespoke parallel write path per composition-service-no-parallel-write-path, retiring the verb ONLY if proven to have no distinct operator purpose beyond calculate/pull and then only with the full documented-command-conformance plus how-to plus suggestion/next_action/help sweep; `src/aeat/entrypoints/cli/_modelo.py`.

### Phase `P04` - One disposition registry plus parity gate

Replace the four scattered enrollment structures (merge_source_resolutions tuple, _pre_mesh_handled, DEFERRED_SOURCE_KINDS, the service provider enum) with one declared mapping answering where every BindingSourceKind member resolves, and extend phase-2.1's mesh parity gate to assert the registry covers every member and equals the union of enrolled resolver owned_sources, making no-dormant-source-resolvers enforceable across the union.

- [x] `P04.S15` - Author one declared disposition mapping keyed by BindingSourceKind member to its resolution state replacing the _pre_mesh_handled and _BUCKET_AGGREGATION_OWNED_SOURCES structures and the service provider enum, re-reading the LIVE mesh sets at execution time so every member carries its HEAD-at-execution disposition including r2's newly-enrolled withholding source as enrolled (not deferred), applying the apply-cached-on-collision drive against the concurrent r2 #28 withholding-enrollment and codex typing WIP; `src/aeat/application/modelo/_calculation_actions.py`.
- [x] `P04.S16` - Re-base the merge_source_resolutions enrollment and the DEFERRED_SOURCE_KINDS set onto the one disposition mapping so a member's resolution state is declared once, re-reading HEAD because r2 #28 moves the withholding source from DEFERRED_SOURCE_KINDS to live enrollment on this surface, applying the apply-cached-on-collision drive against the concurrent r2 and codex WIP; `src/aeat/application/aggregation/_source_mesh.py`.
- [x] `P04.S17` - Extend the phase-2.1 mesh parity gate to assert the disposition registry covers every BindingSourceKind member and equals the union of enrolled resolver owned_sources, reading the LIVE mesh sets at run time with no hard-coded dispositions so r2's newly-enrolled withholding source is reflected automatically, making no-dormant-source-resolvers enforceable across the union; `src/aeat/application/modelo/tests/test_binding_source_kind_mesh_parity.py`.

### Phase `P05` - Prove the unified resolver contract green

Prove the full bindings, calculate, and roundtrip surfaces green plus the extended disposition parity gate, confirm zero vestigial envelope definitions remain, verify no casilla value shifted, and owner-triage the full collect-only tree.

- [ ] `P05.S18` - Run the full bindings, calculate, and roundtrip test surface plus the extended disposition parity gate and confirm green with zero vestigial envelope definitions remaining and no casilla value shifted, then owner-triage the full collect-only tree; `src/aeat/application/modelo/tests/test_binding_source_kind_mesh_parity.py`.

## Description

Implements phase 2.2 (resolver-contract unification) of the bindings-architecture-unification sweep, against the design authority in the phase-2.2 ADR and the breadth-audit anchors F2 (three unreconciled resolver-contract shapes plus four-to-six overlapping result envelopes) and F5 (enrollment state tracked in four disconnected structures, with live capacity silently orphaned).

The work collapses the resolver layer onto one port and one envelope. Today a non-registry source value is produced through one of three structurally distinct contracts: (A) the source mesh, the `ModeloSourceResolver` port returning the rich `CalculationSourceResolution`; (B) a pre-mesh `BindingSourceResolution` Protocol returning `ProfileSourcedBindingResult` / `Modelo100BorradorBindingResult`, where a profile value is shape-converted B-to-A-to-B on every calculation; and (C) the per-modelo aggregation service `aggregate_per_modelo` returning `PerModeloAggregationResult`, where counterpart 347/349 and foreign-assets 720 are reachable ONLY here and never enter the live calculate mesh, and retenciones is reachable through BOTH A and C. Beyond the three live shapes, vestigial envelopes model the same role: `CalculationBindingResolution`, the M349-only `PerModeloRegistryBindingResolution`, the consumer-less `ModeloLedgerBindingAggregation`, and the advertised-but-bypassed `CasillaAggregation` canonical framing.

P01 retires the vestigial envelopes onto the one `CalculationSourceResolution`, migrating each one's few real consumers first. P02 folds profile and borrador into the mesh as first-class `ModeloSourceResolver`s consumed through `merge_source_resolutions`, ending the B-to-A-to-B wrap and removing the `BindingSourceResolution` Protocol, while preserving the caller-override precedence ladder and the borrador provenance trace the downstream observation builder consumes. P03 adjudicates shape C: counterpart 347/349 and foreign-assets 720 join the live mesh as resolvers (closing the orphan), each gated by an explicit per-source correctness check because a folded source now RESOLVES rather than advisory-defers (an enrolled-but-wrong resolver under-declares silently, worse than a visible deferral); retenciones collapses to one mesh path, also correctness-gated; and the CLI aggregate verb is KEPT as a thin delegating projection per `composition-service-no-parallel-write-path` whose aggregation delegates to the one mesh resolver and whose persist-retencion-observations side-effect delegates to the existing single-writer observation repository, never a bespoke parallel write. P04 replaces the four scattered enrollment structures with one disposition registry keyed by `BindingSourceKind` member and extends phase-2.1's mesh parity gate to make `no-dormant-source-resolvers` enforceable across the union. P05 proves the whole surface green with no casilla value shift.

This plan depends on phase-2.1 (`2026-06-26-binding-source-kind-taxonomy-unification-plan`) landing first: the disposition registry and the parity gate are typed on the one `BindingSourceKind` authority phase-2.1 establishes, and they extend phase-2.1's `test_binding_source_kind_mesh_parity.py` gate. Phase-2.2 EXECUTION sequences after phase-2.1 lands.

The lift is behaviour-preserving. The shape-C fold (P03) carries the only real correctness risk: counterpart 347/349, foreign-assets 720, and retenciones must produce identical aggregation output against the existing suites, with no casilla value shift. The profile/borrador fold (P02) must preserve the caller-override precedence ladder and the borrador snapshot-id and `bindings_sourced_from_borrador` provenance trace exactly. Retiring the vestigial envelopes (P01) requires migrating their few real consumers before deletion, in one atomic relocation commit per symbol per `aeat-architecture-boundaries` (one symbol = one commit, `relocation:<symbol>` tag, docs-scaffold and API-stub regen in the same commit), consuming cross-package primitives through top-level `__all__` re-exports per `service-imports-via-top-level-reexports`.

Shared-branch discipline. This plan rides the report-before-land gate: the coordinator reviews this plan before any Step lands, and each landing Step is reported before commit. `_calculation_actions.py` carries live peer WIP (the codex casilla-id-canonicalization sweep and the #28 / RET-1 retenciones campaign), so every Step touching it (S07, S08, S09, S12, S15) re-reads HEAD and `git diff` immediately before editing, aborts on non-authored WIP, and lands its own hunks through the apply-cached-on-collision gated drive (stage a HEAD-anchored own-edits-only patch, verify zero foreign markers, commit the index) rather than overwriting or bundling peer work.

## Parallelization

The whole plan EXECUTION is gated to start AFTER phase-2.1 lands (the disposition registry and parity gate are typed on phase-2.1's `BindingSourceKind` authority and extend its mesh parity gate). Within that gate the phases are hard-ordered: P01 (retire envelopes) before P02 (fold profile/borrador) before P03 (fold shape C) before P04 (disposition registry) before P05 (final gate). P04 must follow P02 and P03 because the disposition registry enumerates the final enrolled set, which is not complete until profile/borrador and counterpart/720 are mesh-enrolled.

Within P01 the three deletion Steps (S01 docstring framing, S02 PerModeloRegistryBindingResolution, S03 ModeloLedgerBindingAggregation) are independent of each other; S04 (re-export surface) co-lands with whichever deletion removes a symbol. Within P02 the two resolver-promotion Steps (S05 profile, S06 borrador) are independent, but the mesh-enrollment Step (S07), the Protocol removal (S08), and the call-site rewrite (S09) are hard-ordered after both and after each other. Within P03 the two resolver-authoring Steps (S10 counterpart, S11 foreign-assets) are independent of each other; the per-source correctness gates S21 (counterpart 347/349) and S20 (foreign-assets 720) follow their resolver Step and MUST pass before S12 enrolls them, so a wrong resolver is caught before it goes live; S12 (enroll + de-defer) follows both correctness gates; S13 (retenciones collapse) is followed by its correctness gate S19 asserting the single mesh path reproduces the prior value exactly; S14 (keep CLI verb as delegating projection) shares the service surface with S13 but is independent of S10-S12. Within P04 the registry Step (S15) precedes the re-base (S16) and the gate extension (S17).

S07, S08, S09, S12, and S15 all touch `_calculation_actions.py` and share the live peer-WIP surface, so they are serialised against each other on that file and each lands through the apply-cached-on-collision drive.

## Verification

- `CalculationSourceResolution` is the only resolved-source envelope: `rg` returns zero definitions of `CalculationBindingResolution`, `PerModeloRegistryBindingResolution`, `ModeloLedgerBindingAggregation`, and the `BindingSourceResolution` Protocol, and the aggregation package docstring no longer advertises `CasillaAggregation` as the bypassed canonical resolved-source framing.
- Profile and borrador resolve through `merge_source_resolutions` as `ModeloSourceResolver`s returning `CalculationSourceResolution` directly; the B-to-A-to-B wrap (`ProfileSourcedBindingResult` / `Modelo100BorradorBindingResult` and `resolve_calculation_binding_inputs`) is removed, and the borrador snapshot-id and `bindings_sourced_from_borrador` provenance trace still reaches the downstream observation builder.
- The caller-override precedence ladder is preserved: the calculate/roundtrip suites prove profile lowest, mesh backend resolvers exclusive, borrador above them, and caller overrides highest, unchanged.
- Counterpart 347/349 and foreign-assets 720 resolve through the live calculate mesh; `FOREIGN_ASSET` is no longer in `DEFERRED_SOURCE_KINDS`; retenciones resolves through ONE mesh path.
- Each folded source is PROVEN correct, not merely enrolled: a per-source correctness gate asserts the live-mesh value equals the prior aggregation output exactly for a 347 fixture, a 349 fixture (S21), a 720 fixture (S20), and the retenciones collapse over 111/115/123/180/190/193 (S19). Because a folded source now resolves rather than advisory-defers, these gates are the guard against a silent under-declaration from an enrolled-but-wrong resolver; the landed perceptor-count result is unchanged and no casilla value shifts.
- The CLI aggregate verb is KEPT as a thin delegating projection: (a) its aggregation delegates to the one mesh resolver with no re-implemented aggregation in the verb, and (b) its persist-retencion-observations side-effect delegates to the existing single-writer observation repository with no bespoke parallel write path, per `composition-service-no-parallel-write-path`. If persist proves to be an import/pull concern it is flagged as a follow-up for the pull-standard surface, not bundled here. The verb is retired only if proven to have no distinct operator purpose beyond calculate/pull, and then only with the full documented-command-conformance plus how-to plus suggestion/next_action/help sweep per `aeat-cli-pull-and-file-standard`.
- One disposition registry keyed by `BindingSourceKind` member replaces the four scattered structures (`merge_source_resolutions` tuple, `_pre_mesh_handled`, `DEFERRED_SOURCE_KINDS`, the service provider enum); the extended `test_binding_source_kind_mesh_parity.py` asserts the registry covers every member and equals the union of enrolled resolver `owned_sources`, making `no-dormant-source-resolvers` enforceable across the union.
- The full bindings, calculate, and roundtrip test surface passes; `uv run --no-sync pytest --collect-only -q src/aeat` is clean; the full-tree gate is owner-triaged.

The plan is complete when every Step is closed and the coordinator has signed off the landed change at the report-before-land gate.
