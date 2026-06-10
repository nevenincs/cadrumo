---
tags:
  - '#plan'
  - '#calculation-engine-foundations'
date: '2026-06-10'
tier: L4
related:
  - '[[2026-06-10-calculation-aggregation-taxonomy-adr]]'
  - '[[2026-06-10-period-revision-resolution-adr]]'
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

# `calculation-engine-foundations` `Calculation-engine foundations: aggregation taxonomy + period-revision resolution` plan

## Epic intent

Implement the two accepted calculation-engine foundation ADRs (aggregation-mechanism taxonomy + period-revision resolution) across most of the backend calculation domain, and make the live operator calculate path the single place every modelo's aggregation actually fires. Strategic goal: no calculation part may be silently dormant — every source resolver, cross-modelo relation, per-period carry, and filing-profile aggregation is either enrolled in the live mesh, or explicitly deferred behind a non-silent advisory, with the full inventory discovered by a sonnet+opus audit swarm and tracked here. External PM association: the 'calculation-engine-foundations' epic on the chore/eliminate-shims factory branch, backed by ADRs 2026-06-10-calculation-aggregation-taxonomy-adr + 2026-06-10-period-revision-resolution-adr and backlog tasks #14/#15 (a GitHub milestone should be opened to mirror it). Timeline: multi-wave; coordinator-orchestrated with per-step code-review gates. Blocks the modelo-130-100-continuity plan and all calculation/filing work until W01-W04 land.

## Wave `W01` - Period to revision resolution engine

Ratify select_revision as the sole law-determined resolver and close D1 (identity-vs-calc divergence), R2 (cross-year carry revision stamp + re-confirmation), and D3 (first-class orden applicability field). Foundational: every aggregation mechanism in later waves consumes the revision this engine resolves. Backs: period-revision-resolution ADR.

### Phase `W01.P01` - Ratify resolver + D1 contract

Ratify select_revision as sole resolver (revision_id assertion-only); strengthen the work-unit creation gate to resolver-equality and add the calc-time snapshot.revision.id == work_unit.revision_id assertion with instructive refusal.

- [x] `W01.P01.S01` - Strengthen resolve_registry_revision_for_work_target to resolver-equality (delegate to select_revision with revision_id, refuse divergent with an instructive message naming requested + law-determined revision); `application/modelo/_work_addressing.py`.
- [x] `W01.P01.S02` - Add the calc-time equality assertion snapshot.revision.id == work_unit.revision_id at every calc entry and refuse on divergence directing operator to re-create the unit; `application/modelo/_calculation_actions.py + _calculate_input.py`.
- [x] `W01.P01.S23` - Ratify select_revision (reached via ValidatedRegistryAuthority.snapshot / resolve_registry_revision_for_work_target) as THE sole law-determined period-to-revision resolver and add a regression that no production calc/verify/filing/export/projection path injects a stored/literal/operator-supplied revision_id into resolution (revision_id is assertion-only), pinning the three benign swept exemptions; `domain/calculations/registry/_temporal.py + _snapshot.py; application/calculations/tests`.

### Phase `W01.P02` - R2 carry revision stamp + gate

Add a revision-provenance field to the persisted observation envelope (producers stamp at write), and a carry-read re-confirmation gate: divergent stamp blocks, missing legacy stamp advises (no-silent), with backfill ratchet.

- [x] `W01.P02.S03` - Add a revision-provenance field to the persisted observation envelope and stamp it at write time from the resolved snapshot across all producers (app filing, sede capture, iva-compensation); `application/calculations/_observations_repository.py + producers; strict roundtrip tests`.
- [x] `W01.P02.S04` - Add the carry-read re-confirmation gate (block on divergent stamp, advise on missing legacy stamp) at every cross-period/cross-year carry read; `application/calculations/_binding_prefill.py + _cross_period_clean_state.py + _multi_year.py`.

### Phase `W01.P03` - D3 first-class orden applicability

Add a mandatory orden_aplicabilidad field per revision.toml, validated against the legal catalogue + BOE corpus per registry-calculation-legal-grounding, merged into legal_refs; hard-cut or ratchet backfill.

- [x] `W01.P03.S05` - Add the orden_aplicabilidad field to the revision schema with registry validation (resolves in legal catalogue, corpus_ref present, merged into legal_refs); `domain/calculations/registry/_schema.py + _validate_revision_rules.py`.
- [x] `W01.P03.S06` - Backfill orden_aplicabilidad across existing revisions (hard-cut if small else ratchet) and require open-ended revisions to cite their open-ended-applicability orden; `registry modelos/**/revisions/*/revision.toml + legal catalogue`.
- [x] `W01.P03.S24` - Document the Ruling-5 (R3) boundary: per-year norm values inside an open-ended *-y-siguientes revision are the parameter-bracket layer's responsibility (validate_bracket_table_temporal_coverage + per-value legal grounding), NOT a resolution defect, and add the connective gate that every open-ended revision's orden_aplicabilidad cites the orden establishing the open-ended applicability; `domain/calculations/registry/_validate_revision_rules.py + .vault/exec boundary note`.

## Wave `W02` - Dormant calculation-parts census and enrollment closure

Turn the sonnet+opus audit-swarm inventory into an explicit tracked list of every dormant, ignored, or unconnected calculation part across renta/iva/sociedades/grupo/informativas, wire collect_unhandled_source_diagnostics into live calculate so nothing blanks silently, and enroll-or-defer-with-advisory each. Backs: aggregation-taxonomy ADR under-declaration closure, expanded to the full discovered inventory.

### Phase `W02.P04` - Dormant-parts census (audit-driven)

Consolidate the sonnet+opus audit-swarm inventory into one explicit tracked list of every dormant/ignored/unconnected calculation part (resolvers, source kinds, relations, per-modelo aggregation, orphans) across renta/iva/sociedades/grupo/informativas.

- [x] `W02.P04.S07` - Consolidate the sonnet+opus audit-swarm inventory into an explicit dormant-parts table in this plan (per item kind, file:line, affected modelos, disposition enroll-or-defer); `.vault audit doc + this plan`.
- [ ] `W02.P04.S25` - Adjudicate the orphan MultiYearResolver (zero callers, no test, PreviousFilingSourceResolver does not delegate to it) and the vestigial cross_period_dependency_inventory/_requirements top-level re-exports: wire into a live path, delete, or document as a named deferral with a follow-up (F7); `application/calculations/_multi_year.py + application/calculations/__init__.py`.

### Phase `W02.P05` - Wire the unhandled-source safety net

Wire collect_unhandled_source_diagnostics into the live calculate path (post-merge) so any binding/relation whose source has no enrolled resolver surfaces a non-blocking advisory on source_diagnostics instead of a silent blank.

- [ ] `W02.P05.S08` - Wire collect_unhandled_source_diagnostics into the live calculate path post-merge so any unrouted source surfaces a non-blocking advisory on source_diagnostics; `application/modelo/_calculation_actions.py + application/aggregation/_source_mesh.py`.
- [ ] `W02.P05.S26` - Turn _BUCKET_AGGREGATION_OWNED_SOURCES from a descriptive constant into an enforced startup/registry gate so every registry binding source kind is a member of the enrolled-resolvers-union-explicitly-deferred-kinds set, failing a novel TOML source that would resolve to blank instead of compiling it silently (F4 boundary half); `application/modelo/_calculation_actions.py + domain/calculations/registry/_validate.py family`.

### Phase `W02.P06` - Enroll-or-defer each inventory item

Enroll the tested dormant resolvers (LedgerRentaIncome, OssIoss, and any audit-discovered others) in the live mesh; for resolver-less source kinds, defer construction with a standing advisory (never on the manual_sources allowlist).

- [ ] `W02.P06.S09` - Enroll the tested dormant resolvers LedgerRentaIncomeAggregationSourceResolver (M130 income), OssIossLedgerSourceResolver (M369 OSS/IOSS), and InvoiceCatalogueSourceResolver (M349 collectible_invoice) in the live merge_source_resolutions tuple with per-resolver real-behaviour enrollment tests (F2); `application/modelo/_calculation_actions.py`.
- [ ] `W02.P06.S10` - For each resolver-less Sheets-pull-only source kind register an explicit deferred disposition behind the standing source_diagnostics advisory and never on the manual_sources allowlist (atribucion_member M184, related_party_operation M232, foreign_asset M720, refund_operation M360 DEFER-with-advisory; `withholding M190/M193 is BUILT in S27, not deferred) (F3); `application/aggregation/_source_mesh.py + registry`.
- [ ] `W02.P06.S27` - BUILD a ModeloSourceResolver for the withholding source kind (M190/M193 per-perceptor retencion rollup, the highest-value F3 pull-only kind) — a real .resolve() projecting the per-perceptor rows the Sheets assemble_* path produces — and enroll it in the live mesh with real-behaviour tests, replacing its DEFER-with-advisory disposition; `application/calculations/_withholding_resolver.py + application/modelo/_calculation_actions.py + tests`.

## Wave `W03` - Aggregation mechanism canonicalization

Make relation canonical for cross-modelo fold-in at the root: introduce the relation_prefill slot source kind, re-stamp mislabelled slot bindings, add the two registry validation gates, enroll RelationPrefillSourceResolver, move relation materialization into the resolver (mesh-guard double-write closure), and declare the precedence ladder. Backs: aggregation-taxonomy ADR rulings 2-5.

### Phase `W03.P07` - Slot-binding hygiene + registry gates

Introduce the relation_prefill slot source kind, re-stamp every relation-targeted non-direct slot binding, and add the two registry validation gates (previous_filing must be direct; no binding both relation-targeted and previous_filing-resolvable).

- [ ] `W03.P07.S11` - Introduce the relation_prefill slot source kind and re-stamp every relation-targeted non-direct slot binding; `registry modelos/**/bindings + domain/calculations/registry`.
- [ ] `W03.P07.S12` - Add the two registry validation gates (previous_filing must satisfy the direct-selector predicate; `no binding both relation-targeted and previous_filing-resolvable); `domain/calculations/registry/_validate.py family`.

### Phase `W03.P08` - Enroll relation resolver + close double-write

Enroll RelationPrefillSourceResolver in the live mesh; move relation target-binding materialization into the resolver so the mesh _claim_binding guard adjudicates collisions; retire the silent post-mesh merge.

- [ ] `W03.P08.S13` - Enroll RelationPrefillSourceResolver in the live mesh and move relation target-binding materialization into the resolver so the mesh ownership guard adjudicates collisions; `retire the silent post-mesh merge; `application/modelo/_calculation_actions.py + _binding_resolution.py + _relation_prefill.py`.
- [ ] `W03.P08.S14` - Real-behaviour test that a relation fold-in fires on live calculate and a relation-vs-other binding collision is refused loudly by the mesh guard; `application/modelo/tests + application/calculations/tests`.

### Phase `W03.P09` - Declared precedence ladder

Codify the D2/D3 precedence out of inline comments into a declared ladder (profile < mesh-backend exclusive-ownership < borrador < caller; caller overrides only previous_filing + relation_prefill; iva_wallet exclusive owner with refusal-on-conflict).

- [ ] `W03.P09.S15` - Codify the declared precedence ladder, extend the D2 caller-override carve-out to relation_prefill carries, keep ledger-owned refusal, reaffirm iva_wallet exclusive-owner; `application/modelo/_calculation_actions.py + _binding_resolution.py`.

## Wave `W04` - Migrations and per-domain fold-in delivery

Migrate M390 to relations under a value-parity gate (M353 exempt), drive every domain's fold-ins live (renta incl. the M100 pagos-fraccionados fold-in + M180/190/193 reconciliations; iva; sociedades M202 period-variant; grupo), and re-baseline affected enrollment/continuity suites against the live path. Backs: both ADRs; absorbs the modelo-130-100-continuity plan.

### Phase `W04.P10` - M390 migration (value-parity)

Migrate the M390 to-M303 cross-modelo previous_filing fold-in bindings to relations under a value-parity gate (identical resolved values before/after, oracle = the existing live-firing path). M353 per_grupo_member stays binding-shaped (exempt, documented revisit trigger).

- [ ] `W04.P10.S16` - Migrate the M390 to-M303 previous_filing fold-in bindings to relations under a value-parity gate and document the M353 per_grupo_member exemption + revisit trigger; `registry modelos/390 + 353; application/calculations/tests`.

### Phase `W04.P11` - Renta fold-ins live + E2E

Drive every renta cross-modelo fold-in live on the operator calculate path: the M100 pagos-fraccionados fold-in (M100 0604 <- sum M130 casilla 19), M184/M111/M115/M123 credits, and the M180<-M115 / M190<-M111 / M193<-M123 reconciliations; E2E autonoma proof, real adapters, anti-tautology.

- [ ] `W04.P11.S17` - Drive the M100 pagos-fraccionados fold-in live (0604 sum of M130 casilla 19 over 1T-4T) with an E2E autonoma proof on the operator calculate path; `registry modelos/100; application/modelo + entrypoints/cli tests`.
- [ ] `W04.P11.S18` - Drive the M180-from-M115, M190-from-M111, M193-from-M123 reconciliations and the M184/M111/M115/M123 renta credits live + E2E; `registry renta modelos; application/calculations/tests`.

### Phase `W04.P12` - Iva/sociedades/other fold-ins live + E2E

Drive iva (M390<-M303), sociedades (M200, M202 period-variant cumulative), and any other audit-discovered domain fold-ins live + E2E; re-baseline affected enrollment/continuity suites against the live calculate path (not the direct-call path).

- [ ] `W04.P12.S19` - Drive iva (M390-from-M303) and sociedades (M200, M202 period-variant cumulative) and audit-discovered domain fold-ins live + E2E; `registry iva/sociedades modelos; tests`.
- [ ] `W04.P12.S20` - Re-baseline the affected enrollment and continuity suites against the live calculate path rather than the direct-call path; `application/calculations/tests + application/modelo/tests`.
- [ ] `W04.P12.S28` - Prove each newly-enrolled DORMANT modelo fires aggregation live on the operator calculate path with an E2E real-adapter anti-tautology proof (M130 income via ledger_renta_income, M369 OSS/IOSS via ledger_oss, M349 invoices via collectible_invoice, M190/M193 withholding via the built resolver) and confirm the still-deferred M184/M232/M720/M360 each emit the standing source_diagnostics advisory rather than a silent blank (F6); `application/modelo/tests + entrypoints/cli/tests`.
- [ ] `W04.P12.S29` - Close the Sheets-pull vs live-calculate drift (F5): unify the six assemble_* row-set functions, resolve_relations_from_local_store, and resolve_modelo_ledger_binding_values_from_repositories onto the one enrolled resolver set so both surfaces share one aggregation logic, and add a regression proving pull-path == calculate-path casilla values for a shared revision; `application/calculations/_row_set_assembly.py + _modelo_bindings.py + application/calculations/tests`.

## Wave `W05` - Codification and epic verification

Codify the ADR rule candidates and any audit-surfaced durable rules, and run an epic-close honesty review + full-suite verification proving no calculation part remains silently dormant. Backs: both ADRs codification sections + aeat-campaign-close-honesty-review.

### Phase `W05.P13` - Codify durable rules

Promote the ADR codification candidates (revision-resolution-is-law-determined; carried-observations-stamp-their-revision; calculation-source-canonical-mechanism; no-dormant-source-resolvers; relation-slot-bindings-declare-relation-source) and any audit-surfaced durable rule via the codify pipeline.

- [ ] `W05.P13.S21` - Promote the ADR and audit codification candidates via the codify pipeline: revision-resolution-is-law-determined and carried-observations-stamp-their-revision (period-revision ADR), calculation-source-canonical-mechanism and no-dormant-source-resolvers and relation-slot-bindings-declare-relation-source (aggregation ADR), and one-aggregation-path-pull-equals-calculate (census F5); `.vaultspec/rules/rules/project`.

### Phase `W05.P14` - Epic-close honesty review + verify

Run a fresh-context honesty review against the epic summary + a full-suite verification proving no calculation part remains silently dormant (the census is empty or every residual carries a tracked advisory + follow-up).

- [ ] `W05.P14.S22` - Run a fresh-context epic-close honesty review against the epic summary and a full-suite verification proving the dormant census is empty or every residual carries a tracked advisory + follow-up; `.vault/audit; full suite`.
