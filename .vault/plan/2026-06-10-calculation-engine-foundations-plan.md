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
- [x] `W02.P04.S25` - Adjudicate the orphan MultiYearResolver (zero callers, no test, PreviousFilingSourceResolver does not delegate to it) and the vestigial cross_period_dependency_inventory/_requirements top-level re-exports: wire into a live path, delete, or document as a named deferral with a follow-up (F7); `application/calculations/_multi_year.py + application/calculations/__init__.py`.

### Phase `W02.P05` - Wire the unhandled-source safety net

Wire collect_unhandled_source_diagnostics into the live calculate path (post-merge) so any binding/relation whose source has no enrolled resolver surfaces a non-blocking advisory on source_diagnostics instead of a silent blank.

- [x] `W02.P05.S08` - Wire collect_unhandled_source_diagnostics into the live calculate path post-merge so any unrouted source surfaces a non-blocking advisory on source_diagnostics; `application/modelo/_calculation_actions.py + application/aggregation/_source_mesh.py`.
- [x] `W02.P05.S26` - Turn _BUCKET_AGGREGATION_OWNED_SOURCES from a descriptive constant into an enforced startup/registry gate so every registry binding source kind is a member of the enrolled-resolvers-union-explicitly-deferred-kinds set, failing a novel TOML source that would resolve to blank instead of compiling it silently (F4 boundary half); `application/modelo/_calculation_actions.py + domain/calculations/registry/_validate.py family`.

### Phase `W02.P06` - Enroll-or-defer each inventory item

Enroll the tested dormant resolvers (LedgerRentaIncome, OssIoss, and any audit-discovered others) in the live mesh; for resolver-less source kinds, defer construction with a standing advisory (never on the manual_sources allowlist).

- [x] `W02.P06.S09` - Enroll the tested dormant resolvers LedgerRentaIncomeAggregationSourceResolver (M130 income), OssIossLedgerSourceResolver (M369 OSS/IOSS), and InvoiceCatalogueSourceResolver (M349 collectible_invoice) in the live merge_source_resolutions tuple with per-resolver real-behaviour enrollment tests (F2); `application/modelo/_calculation_actions.py`.
- [x] `W02.P06.S10` - For each resolver-less Sheets-pull-only source kind register an explicit deferred disposition behind the standing source_diagnostics advisory and never on the manual_sources allowlist (atribucion_member M184, related_party_operation M232, foreign_asset M720, refund_operation M360, withholding M190/M193 — all DEFER-with-advisory; `withholding adjudicated to defer in S27, no live per-perceptor source) (F3); `application/aggregation/_source_mesh.py + registry`.
- [x] `W02.P06.S27` - Adjudicate the withholding source kind (M190/M193 per-perceptor detalle) as DEFER-with-advisory, NOT built: the per-perceptor rows live only in the Sheets detalle tab and the transaction ledger carries no retencion/perceptor breakdown, so a live .resolve() has no source to read (a built resolver would be an empty design-only shell). Align it with the other four detalle deferred kinds; `lock the standing source_diagnostics advisory with a regression test; correct the DEFERRED_SOURCE_KINDS comment. A real ledger-derived withholding build is a future feature (new ingest surface) tracked separately (F3); `application/aggregation/_source_mesh.py + application/modelo/tests/test_source_boundary_and_enrollment.py`.

## Wave `W03` - Aggregation mechanism canonicalization

Make relation canonical for cross-modelo fold-in at the root: introduce the relation_prefill slot source kind, re-stamp mislabelled slot bindings, add the two registry validation gates, enroll RelationPrefillSourceResolver, move relation materialization into the resolver (mesh-guard double-write closure), and declare the precedence ladder. Backs: aggregation-taxonomy ADR rulings 2-5.

### Phase `W03.P07` - Slot-binding hygiene + registry gates

Introduce the relation_prefill slot source kind, re-stamp every relation-targeted non-direct slot binding, and add the two registry validation gates (previous_filing must be direct; no binding both relation-targeted and previous_filing-resolvable).

- [x] `W03.P07.S11` - Introduce the relation_prefill slot source kind and re-stamp every relation-targeted non-direct slot binding; `registry modelos/**/bindings + domain/calculations/registry`.
- [x] `W03.P07.S12` - Add the two registry validation gates (previous_filing must satisfy the direct-selector predicate; `no binding both relation-targeted and previous_filing-resolvable); `domain/calculations/registry/_validate.py family`.

### Phase `W03.P08` - Enroll relation resolver + close double-write

Enroll RelationPrefillSourceResolver in the live mesh; move relation target-binding materialization into the resolver so the mesh _claim_binding guard adjudicates collisions; retire the silent post-mesh merge.

- [x] `W03.P08.S13` - Enroll RelationPrefillSourceResolver in the live mesh and move relation target-binding materialization into the resolver so the mesh ownership guard adjudicates collisions; `retire the silent post-mesh merge; `application/modelo/_calculation_actions.py + _binding_resolution.py + _relation_prefill.py`.
- [x] `W03.P08.S14` - Real-behaviour test that a relation fold-in fires on live calculate and a relation-vs-other binding collision is refused loudly by the mesh guard; `application/modelo/tests + application/calculations/tests`.

### Phase `W03.P09` - Declared precedence ladder

Codify the D2/D3 precedence out of inline comments into a declared ladder (profile < mesh-backend exclusive-ownership < borrador < caller; caller overrides only previous_filing + relation_prefill; iva_wallet exclusive owner with refusal-on-conflict).

- [x] `W03.P09.S15` - Codify the declared precedence ladder, extend the D2 caller-override carve-out to relation_prefill carries, keep ledger-owned refusal, reaffirm iva_wallet exclusive-owner; `application/modelo/_calculation_actions.py + _binding_resolution.py`.

## Wave `W04` - Migrations and per-domain fold-in delivery

Migrate M390 to relations under a value-parity gate (M353 exempt), drive every domain's fold-ins live (renta incl. the M100 pagos-fraccionados fold-in + M180/190/193 reconciliations; iva; sociedades M202 period-variant; grupo), and re-baseline affected enrollment/continuity suites against the live path. Backs: both ADRs; absorbs the modelo-130-100-continuity plan.

### Phase `W04.P10` - M390 migration (value-parity)

Migrate the M390 to-M303 cross-modelo previous_filing fold-in bindings to relations under a value-parity gate (identical resolved values before/after, oracle = the existing live-firing path). M353 per_grupo_member stays binding-shaped (exempt, documented revisit trigger).

- [x] `W04.P10.S16` - Migrate the M390 to-M303 previous_filing fold-in bindings to relations under a value-parity gate and document the M353 per_grupo_member exemption + revisit trigger; `registry modelos/390 + 353; application/calculations/tests`.

### Phase `W04.P11` - Renta fold-ins live + E2E

Drive every renta cross-modelo fold-in live on the operator calculate path: the M100 pagos-fraccionados fold-in (M100 0604 <- sum M130 casilla 19), M184/M111/M115/M123 credits, and the M180<-M115 / M190<-M111 / M193<-M123 reconciliations; E2E autonoma proof, real adapters, anti-tautology.

- [x] `W04.P11.S17` - Drive the M100 pagos-fraccionados fold-in live (0604 sum of M130 casilla 19 over 1T-4T) with an E2E autonoma proof on the operator calculate path; `registry modelos/100; application/modelo + entrypoints/cli tests`.
- [x] `W04.P11.S18` - Drive the M180-from-M115, M190-from-M111, M193-from-M123 reconciliations and the M184/M111/M115/M123 renta credits live + E2E; `registry renta modelos; application/calculations/tests`.
- [x] `W04.P11.S30` - Drive the M100 retenciones-credit fold-ins live + E2E (the 1809/1807/0149/0221/0222/0224/0218/1813/1845/1846/1811/0422/0423 retenciones-credit casillas folding from 111/115/123/180/184 relations) reusing the S17 M100 binding scaffold (profile seed + non-relation zero bindings) — carved out of S18 because the M100 credit casillas need per-formula source tracing distinct from the standalone annual reconciliations; `registry modelos/100; application/modelo/tests`.
- [ ] `W04.P11.S34` - Triage the 25 calibrated orphaned M100 cross-period relations (coordinator registry sweep: relation neither formula-referenced nor casilla-bound) — M100/2020-2023 retenciones from 111/115/123 (x4 each), M100/2024 rel-115-retenciones-trimestrales + rel-193-retenciones-anuales, M100/2025 retenciones from 111/115/123/180/190/193 + pagos 130/131. The wiring is inconsistent across revision years (only M100/2024 0604 pagos is wired, by S17). For EACH orphan determine via live calc: (a) should-fold-but-doesnt -> wire the credit/pagos casilla + legal-ground + prove live; `(b) feeds an intentionally-manual casilla (operator enters retenciones from certificados) -> document as by-design; (c) folds via a path the static sweep missed (like M200 DP200014B:00611 formula relation-operand) -> confirm + prove. Apply the M200 false-alarm lesson: do NOT wire blindly. S30 informs the retenciones-credit subset; `registry modelos/100 + legal catalogue; application/modelo/tests`.

### Phase `W04.P12` - Iva/sociedades/other fold-ins live + E2E

Drive iva (M390<-M303), sociedades (M200, M202 period-variant cumulative), and any other audit-discovered domain fold-ins live + E2E; re-baseline affected enrollment/continuity suites against the live calculate path (not the direct-call path).

- [x] `W04.P12.S19` - Drive iva (M390-from-M303) and sociedades (M200, M202 period-variant cumulative) and audit-discovered domain fold-ins live + E2E; `registry iva/sociedades modelos; tests`.
- [ ] `W04.P12.S20` - Re-baseline the affected enrollment and continuity suites against the live calculate path rather than the direct-call path; `application/calculations/tests + application/modelo/tests`.
- [x] `W04.P12.S28` - Prove each newly-enrolled DORMANT modelo fires aggregation live on the operator calculate path with an E2E real-adapter anti-tautology proof (M130 income via ledger_renta_income, M369 OSS/IOSS via ledger_oss, M349 invoices via collectible_invoice) and confirm the still-deferred detalle kinds (withholding M190/M193, atribucion_member M184, related_party_operation M232, foreign_asset M720, refund_operation M360) each emit the standing source_diagnostics advisory rather than a silent blank (F6; `withholding is DEFER-with-advisory per S27 — NOT a built resolver); `application/modelo/tests + entrypoints/cli/tests`.
- [ ] `W04.P12.S29` - Close the Sheets-pull vs live-calculate drift (F5): unify the six assemble_* row-set functions, resolve_relations_from_local_store, and resolve_modelo_ledger_binding_values_from_repositories onto the one enrolled resolver set so both surfaces share one aggregation logic, and add a regression proving pull-path == calculate-path casilla values for a shared revision; `application/calculations/_row_set_assembly.py + _modelo_bindings.py + application/calculations/tests`.
- [ ] `W04.P12.S31` - Engine robustness (coordinator ruling c, finding #26 surfaced by S17/S18): a cross-modelo fold-in relation with NO or PARTIAL prior filing MUST resolve its target casilla to blank/unresolved plus a non-blocking source_diagnostics advisory naming the missing modelo+periods, NOT raise RegistryValidationError 'relation has no supplied value' (current _formula_runtime.py behaviour) and NOT silently zero-contribute (would under-declare); `preserve found-0 vs genuine-wiring-bug distinction; land AFTER the happy-path matrix (S17/S18/S19/S28) so those proofs guard the raise-to-blank semantics change; `domain/calculations/registry/_formula_runtime.py + application/calculations/_relation_prefill.py + application/aggregation/_source_mesh.py; tests`.
- [ ] `W04.P12.S32` - Activate the M200<-M202 pagos-fraccionados-anuales fold (DEAD WIRING found by S19): the relation modelo-200-2024-rel-202-pagos-fraccionados + target binding modelo-200-2024-pagos-fraccionados-anuales exist but NO M200/2024 casilla consumes the binding (casilla 00601 is_pagos_fraccionados is still manual), so the cross-modelo fold never reaches a casilla value (F1-class silent gap the census missed at the casilla level). Wire casilla 00601 to the binding (manual->bound/computed) WITH legal grounding (M200 instruction: pagos fraccionados deducibles = sum of the year's M202 instalments; `cite the binding source) and complete the carved-out S19 live E2E proof that the M200 pagos casilla == sum of M202 1P/2P/3P output 34; `registry modelos/200 + legal catalogue; application/modelo/tests/test_modelo_202_sociedades_fold_in_live.py`.
- [ ] `W04.P12.S33` - Build the M369 OSS/IOSS ledger projection (DEAD WIRING found by S28): the live path hard-wires OssIossLedgerSourceResolver(candidates=()) and there is NO ledger->OssIossLedgerCandidate projection in the codebase (the resolver is sound at the mesh boundary but nothing feeds it on the live path), so real OSS data resolves to a claimed-zero. Build aggregate_oss_ioss_*_from_repositories(bucket_id, period, ...) projecting bucket ledger lines (cross-border B2C distance/digital sales, per esquema union/import/exterior) into OssIossLedgerCandidate, wire it into _calculation_actions.py (replacing candidates=()), and complete the carved-out S28 OSS live E2E proof; `ground the OSS classification in the registry/regulatory source; `application/aggregation/_oss_ioss.py + application/modelo/_calculation_actions.py; application/modelo/tests/test_dormant_ledger_resolvers_fire_live.py`.

## Wave `W05` - Codification and epic verification

Codify the ADR rule candidates and any audit-surfaced durable rules, and run an epic-close honesty review + full-suite verification proving no calculation part remains silently dormant. Backs: both ADRs codification sections + aeat-campaign-close-honesty-review.

### Phase `W05.P13` - Codify durable rules

Promote the ADR codification candidates (revision-resolution-is-law-determined; carried-observations-stamp-their-revision; calculation-source-canonical-mechanism; no-dormant-source-resolvers; relation-slot-bindings-declare-relation-source) and any audit-surfaced durable rule via the codify pipeline.

- [ ] `W05.P13.S21` - Promote the ADR and audit codification candidates via the codify pipeline: revision-resolution-is-law-determined and carried-observations-stamp-their-revision (period-revision ADR), calculation-source-canonical-mechanism and no-dormant-source-resolvers and relation-slot-bindings-declare-relation-source (aggregation ADR), and one-aggregation-path-pull-equals-calculate (census F5); `.vaultspec/rules/rules/project`.

### Phase `W05.P14` - Epic-close honesty review + verify

Run a fresh-context honesty review against the epic summary + a full-suite verification proving no calculation part remains silently dormant (the census is empty or every residual carries a tracked advisory + follow-up).

- [ ] `W05.P14.S22` - Run a fresh-context epic-close honesty review against the epic summary and a full-suite verification proving the dormant census is empty or every residual carries a tracked advisory + follow-up; `.vault/audit; full suite`.
