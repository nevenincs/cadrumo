---
tags:
  - '#plan'
  - '#source-casilla-integration'
date: '2026-08-22'
tier: L3
related:
  - '[[2026-08-22-source-casilla-integration-adr]]'
  - '[[2026-08-22-source-casilla-integration-research]]'
  - '[[2026-08-22-modelo-work-binding-architecture-inventory-gap-verification-reference]]'
modified: '2026-08-23'
body_schema: body-v1
body_hash: 'sha256:812b7e18ed0c14b2a81296027eedbc769b5745baa6b7dee1abe1e788e2337726'
---

# `source-casilla-integration` plan

Build and enforce the source-domain-to-casilla connectivity census, then adjudicate and deliver inventory, amortization, and every remaining evidence-backed disconnected source through the canonical calculation architecture.

## Description

This plan executes the accepted source-casilla integration decision. Wave W01 establishes the canonical census, discovery instrument, closed dispositions, and monotonic enforcement gate. Wave W02 adjudicates and, where officially supported, connects inventory as the first production vertical slice. Wave W03 does the same for amortization as the mandatory second slice. Wave W04 resolves the remaining typed-domain candidates, including assets and fincas. Wave W05 resolves each currently deferred row source independently. Wave W06 reruns discovery, closes every remaining candidate honestly, aligns documentation, and obtains final formal reviews.

Every candidate must reach exactly one allowed disposition. A production connection requires official tax grounding, canonical source taxonomy and selector validation, registry binding and casilla linkage, resolver ownership, explicit override policy, diagnostics, provenance, encrypted revision round trip, operator-path proof, and replay, review, and export proof where those surfaces are supported. Lexical or numeric casilla similarity cannot authorize a connection.

## Steps

## Wave `W01` - establish the canonical connectivity census and ratchet

Create the authoritative, machine-checkable inventory of registry destinations and source capabilities; all later Waves depend on its closed classification vocabulary and enforcement gates.

### Phase `W01.P01` - define the census contract

Define the typed candidate identity, evidence, ownership, disposition, expiry, and proof model.

- [x] `W01.P01.S01` - define the closed connectivity disposition taxonomy and candidate identity model; `src/cadrumo/core/source_connectivity.py`.
- [x] `W01.P01.S02` - define grounding, ownership, review-condition, expiry, and bounded-follow-up fields; `src/cadrumo/core/source_connectivity.py`.
- [x] `W01.P01.S03` - define the connected-slice proof contract for resolver ownership, revision persistence, and operator reachability; `src/cadrumo/core/source_connectivity.py`.
- [x] `W01.P01.S04` - expose the canonical connectivity models through the core public surface; `src/cadrumo/core/__init__.py`.
- [x] `W01.P01.S05` - verify invalid dispositions, incomplete blocked rows, expired review conditions, and unsupported connected claims are refused; `src/cadrumo/core/tests/test_source_connectivity.py`.
- [x] `W01.P01.S136` - extend connected authority validation with the full encrypted-revision proof and refuse persisted identity or fingerprint drift; `src/cadrumo/core`.
- [x] `W01.P01.S138` - replace raw source-object identity with the exact persisted source reference across connected proof; `src/cadrumo/core`.
- [x] `W01.P01.S139` - align connected source-reference validation exactly with persisted CalculationSourceRef semantics; `src/cadrumo/core`.
- [x] `W01.P01.S137` - project supported modelo calculation workflows from the reconciled live operator surface; `src/cadrumo/application/operator_surface`.
- [x] `W01.P01.S134` - implement the concrete connected-proof authority from live source enrollment, supported workflow catalogues, repository evidence digests, and encrypted revision reads; `src/cadrumo/application/registry`.
- [x] `W01.P01.S140` - centralize the production modelo-work calculation route and its staged resolver ownership so runtime composition and authority share one declaration; `src/cadrumo/application/modelo`.
- [x] `W01.P01.S146` - make calculation-route ownership validation refuse renamed resolvers, invented pseudo-owners, and stage drift; `src/cadrumo/application/modelo`.
- [x] `W01.P01.S145` - persist resolver identity through calculation source provenance and encrypted revision round trips; `src/cadrumo`.
- [x] `W01.P01.S147` - make persisted source provenance internally coherent, identity-bearing, unambiguous, and strictly typed; `src/cadrumo`.
- [x] `W01.P01.S148` - require source provenance at every revision identity and persistence boundary and correct its identity contract; `src/cadrumo`.
- [x] `W01.P01.S141` - bind operator workflow authority validation to the full source connection identity; `src/cadrumo/core`.
- [x] `W01.P01.S142` - attach canonical calculation-route identity to reconciled supported operator workflows; `src/cadrumo/application/operator_surface`.
- [x] `W01.P01.S143` - derive live proof enrollment and exact workflow reachability from canonical calculation-route ownership; `src/cadrumo/application/registry`.
- [x] `W01.P01.S144` - make repository evidence digest verification descriptor-safe against path replacement races; `src/cadrumo/application/registry`.
- [x] `W01.P01.S149` - define the canonical primary/contributor lineage role and replace the calculation-source provenance shape atomically with separate resolved and contributor axes; `src/cadrumo/core; src/cadrumo/domain/modelos`.
- [x] `W01.P01.S150` - migrate every calculation-source provenance constructor, serializer, merge, and revision-identity payload without defaults, aliases, or dual-read compatibility; `src/cadrumo/application; src/cadrumo/adapters; src/cadrumo/domain`.
- [x] `W01.P01.S151` - emit IVA wallet decisions as immutable event-key primaries and parent their authority-source contributors to the decision provenance node; `src/cadrumo/application/calculations; src/cadrumo/application/aggregation`.
- [x] `W01.P01.S152` - classify the M720 foreign-asset composite as grounding-blocked until a typed unique resolved-asset identity or separately approved uniqueness-enforced key exists; `src/cadrumo/application/aggregation; .vault`.
- [x] `W01.P01.S153` - make live connectivity authority accept exactly one resolver-matching primary and reject contributor-only, ambiguous, orphaned, drifted, or malformed provenance graphs; `src/cadrumo/application/registry`.
- [x] `W01.P01.S154` - verify composite and direct provenance identity, encrypted round trips, mutation refusal, wallet lineage, foreign-asset blocking, and semantic sentinel non-duplication; `src/cadrumo`.
- [x] `W01.P01.S155` - correct composite-provenance documentation and validation language identified by formal review; `src/cadrumo/domain/modelos`.
- [x] `W01.P01.S135` - replace the configurable proof fake with real authority and encrypted-revision mutation coverage; `src/cadrumo/application/registry/tests/test_source_connectivity_authority.py`.

### Phase `W01.P02` - derive the registry-side inventory

Produce deterministic records for every validated manual casilla, binding, relation, formula, and source disposition.

- [x] `W01.P02.S06` - derive registry destination records from validated revision snapshots; `src/cadrumo/application/registry/source_connectivity.py`.
- [x] `W01.P02.S07` - classify manual casillas without inferring substitutability from labels or numeric identifiers; `src/cadrumo/application/registry/source_connectivity.py`.
- [x] `W01.P02.S08` - project declared bindings, typed selectors, aggregation operations, and target casillas; `src/cadrumo/application/registry/source_connectivity.py`.
- [x] `W01.P02.S09` - project relations, formula dependencies, and existing source dispositions; `src/cadrumo/application/registry/source_connectivity.py`.
- [x] `W01.P02.S10` - verify all loaded modelo revisions produce deterministic registry-side census records; `src/cadrumo/application/registry/tests/test_source_connectivity_inventory.py`.

### Phase `W01.P03` - derive the source-capability inventory

Enumerate typed secure domains, repositories, ingress, assemblers, helpers, and readiness declarations without treating a name match as authority.

- [x] `W01.P03.S11` - enumerate secure typed repositories and their aggregate grains; `dev/source_connectivity/discovery.py`.
- [x] `W01.P03.S12` - enumerate supported CLI and worksheet ingress surfaces; `dev/source_connectivity/discovery.py`.
- [x] `W01.P03.S13` - enumerate exported calculation helpers and explicit readiness declarations; `dev/source_connectivity/discovery.py`.
- [x] `W01.P03.S14` - enumerate typed row assemblers and declared source-disposition ownership; `dev/source_connectivity/discovery.py`.
- [x] `W01.P03.S15` - emit lexical destination matches as advisory findings only; `dev/source_connectivity/discovery.py`.
- [x] `W01.P03.S16` - verify discovery detects a new repository, assembler, helper, and readiness declaration independently; `dev/source_connectivity/tests/test_discovery.py`.

### Phase `W01.P04` - publish the canonical census

Join both inventories through reviewed evidence-backed records and establish the initial complete classification.

- [x] `W01.P04.S17` - define the canonical machine-readable census manifest; `src/cadrumo/_data/source_connectivity/census.toml`.
- [x] `W01.P04.S18` - load and validate the census against the closed contract; `src/cadrumo/application/registry/source_connectivity.py`.
- [x] `W01.P04.S19` - classify inventory as the first adjudication candidate with the obsolete 0155 hazard recorded; `src/cadrumo/_data/source_connectivity/census.toml`.
- [x] `W01.P04.S20` - classify amortization as the mandatory second adjudication candidate; `src/cadrumo/_data/source_connectivity/census.toml`.
- [x] `W01.P04.S21` - classify assets and fincas with separate evidence, grain, and substitutability questions; `src/cadrumo/_data/source_connectivity/census.toml`.
- [x] `W01.P04.S22` - classify each of the five deferred row sources as an independent candidate; `src/cadrumo/_data/source_connectivity/census.toml`.
- [x] `W01.P04.S23` - verify every discovered capability and accepted destination candidate has exactly one census row; `dev/source_connectivity/tests/test_census_completeness.py`.

### Phase `W01.P05` - enforce the monotonic ratchet

Make silent capability drift, stale deferral, and false connection claims fail CI.

- [x] `W01.P05.S24` - implement census generation and comparison commands; `dev/source_connectivity/cli.py`.
- [x] `W01.P05.S25` - reject unclassified new source capabilities and unexplained candidate disappearance; `dev/source_connectivity/check.py`.
- [x] `W01.P05.S26` - reject expired blocked rows and unresolved rows without an owner and bounded follow-up; `dev/source_connectivity/check.py`.
- [x] `W01.P05.S27` - reject connected claims without resolver ownership and encrypted revision proof; `dev/source_connectivity/check.py`.
- [ ] `W01.P05.S28` - prove each ratchet failure mode bites under an external mutation; `dev/source_connectivity/tests/test_check.py`.
- [ ] `W01.P05.S29` - enroll the connectivity check in the repository quality-gate surface; `pyproject.toml`.
- [ ] `W01.P05.S30` - conduct a formal code review of the census and ratchet foundation; `.vault/audit/2026-08-22-source-casilla-integration-census-code-review.md`.

## Wave `W02` - adjudicate and connect inventory first

Resolve the inventory tax mapping before changing production behavior, then deliver the complete canonical slice if and only if official evidence proves the mapping.

### Phase `W02.P06` - adjudicate inventory semantics

Settle revision coverage, source facts, sign, units, activity grain, absence semantics, and override ownership.

- [ ] `W02.P06.S31` - ground M100 inventory increase, purchases, and decrease semantics against official AEAT and BOE sources; `.vault/research/2026-08-22-inventory-casilla-grounding-research.md`.
- [ ] `W02.P06.S32` - adjudicate the mapping from opening stock, purchase movements, and closing stock to 0177, 0181, and 0182; `.vault/adr/2026-08-22-inventory-casilla-mapping-adr.md`.
- [ ] `W02.P06.S33` - decide revision windows, activity aggregation, sign, rounding, missing-ledger behavior, and caller override policy; `.vault/adr/2026-08-22-inventory-casilla-mapping-adr.md`.
- [ ] `W02.P06.S34` - remove or correct the stale Anexo D casilla 0155 intent after adjudication; `src/cadrumo/domain/contribuyente/inventory/__init__.py`.
- [ ] `W02.P06.S35` - record the adjudicated inventory disposition and re-fetchable evidence; `src/cadrumo/_data/source_connectivity/census.toml`.

### Phase `W02.P07` - implement the inventory source contract

Add inventory to the canonical taxonomy and resolution mesh without bypassing secure domain ownership.

- [ ] `W02.P07.S36` - add the inventory source kind to the canonical taxonomy; `src/cadrumo/core/aggregation.py`.
- [ ] `W02.P07.S37` - define and validate the typed inventory selector contract; `src/cadrumo/domain/calculations/registry/_inventory_bindings.py`.
- [ ] `W02.P07.S38` - enroll inventory selector validation in registry binding construction; `src/cadrumo/domain/calculations/registry/_bindings.py`.
- [ ] `W02.P07.S39` - implement inventory repository resolution, diagnostics, source identity, and fingerprint provenance; `src/cadrumo/application/aggregation/_inventory.py`.
- [ ] `W02.P07.S40` - enroll the inventory resolver and explicit source disposition; `src/cadrumo/application/aggregation/_source_mesh.py`.
- [ ] `W02.P07.S41` - supply the encrypted inventory repository through calculation orchestration; `src/cadrumo/application/modelo/_calculation_actions.py`.
- [ ] `W02.P07.S42` - enforce inventory source ownership and caller-override refusal; `src/cadrumo/application/modelo/_calculate_input.py`.

### Phase `W02.P08` - bind inventory into the legal registry

Declare only the revision-specific facts established by adjudication.

- [ ] `W02.P08.S43` - add grounded inventory bindings for supported M100 revisions; `src/cadrumo/_data/registry/aeat/modelos/100/revisions`.
- [ ] `W02.P08.S44` - link inventory bindings to the adjudicated M100 casillas; `src/cadrumo/_data/registry/aeat/modelos/100/revisions`.
- [ ] `W02.P08.S45` - verify inventory selector shape, legal references, source references, and casilla linkage; `src/cadrumo/domain/calculations/registry/tests/test_inventory_bindings.py`.

### Phase `W02.P09` - prove the inventory vertical slice

Prove the real encrypted and operator-facing path, including negative and conflict behavior.

- [ ] `W02.P09.S46` - prove inventory values cross the real encrypted CalculationRevision boundary with strict equality; `src/cadrumo/adapters/persistence/profile/tests/test_inventory_source_revision_roundtrip.py`.
- [ ] `W02.P09.S47` - prove deleting persisted inventory provenance is detected by the round-trip gate; `src/cadrumo/adapters/persistence/profile/tests/test_inventory_source_revision_roundtrip.py`.
- [ ] `W02.P09.S48` - prove missing, incomplete, and unreadable inventory emit actionable diagnostics; `src/cadrumo/application/modelo/tests/test_inventory_source_mesh.py`.
- [ ] `W02.P09.S49` - prove caller values cannot collide with or replace inventory-owned values; `src/cadrumo/application/modelo/tests/test_inventory_source_mesh.py`.
- [ ] `W02.P09.S50` - prove the CLI create-to-calculate-to-review workflow reaches the inventory resolver; `src/cadrumo/entrypoints/cli/tests/test_inventory_modelo_workflow.py`.
- [ ] `W02.P09.S51` - prove recalculation and review preserve source identity, fingerprint, and grounding; `src/cadrumo/application/modelo/tests/test_inventory_replay_review.py`.
- [ ] `W02.P09.S52` - prove supported export output consumes the frozen inventory-derived casillas; `src/cadrumo/application/filing/tests/test_inventory_export.py`.
- [ ] `W02.P09.S53` - update inventory readiness to reflect only capabilities proven by the landed slice; `src/cadrumo/application/inventory/_source_readiness.py`.
- [ ] `W02.P09.S54` - promote inventory to connected only after every connected proof passes; `src/cadrumo/_data/source_connectivity/census.toml`.
- [ ] `W02.P09.S55` - conduct a formal code review of the inventory vertical slice; `.vault/audit/2026-08-22-inventory-casilla-connection-code-review.md`.

## Wave `W03` - adjudicate and connect amortization second

Resolve whether the asset and finca amortization ledgers are authoritative filing sources or duplicate already-booked ledger expenses, then deliver every proven amortization connection.

### Phase `W03.P10` - adjudicate amortization semantics

Settle filing destination identity, substitutability, grain, precedence, absence semantics, rounding, and override policy.

- [ ] `W03.P10.S56` - ground amortization destinations, revision windows, eligible basis, rates, limits, and asset grain; `.vault/research/2026-08-22-amortization-casilla-grounding-research.md`.
- [ ] `W03.P10.S57` - determine whether asset amortization is a direct filing source or a duplicate of transaction-ledger expenses; `.vault/adr/2026-08-22-amortization-casilla-mapping-adr.md`.
- [ ] `W03.P10.S58` - determine whether finca amortization shares or requires a distinct source contract; `.vault/adr/2026-08-22-amortization-casilla-mapping-adr.md`.
- [ ] `W03.P10.S59` - decide grain, precedence, absence semantics, rounding, and override policy; `.vault/adr/2026-08-22-amortization-casilla-mapping-adr.md`.
- [ ] `W03.P10.S60` - record separate asset-amortization and finca-amortization dispositions; `src/cadrumo/_data/source_connectivity/census.toml`.

### Phase `W03.P11` - implement the amortization vertical slice

Deliver each adjudicated amortization connection through the canonical taxonomy, registry, resolver, secure persistence, and operator path.

- [ ] `W03.P11.S61` - add the adjudicated amortization source kind or kinds to the canonical taxonomy; `src/cadrumo/core/aggregation.py`.
- [ ] `W03.P11.S62` - define and validate typed amortization selectors; `src/cadrumo/domain/calculations/registry/_amortization_bindings.py`.
- [ ] `W03.P11.S63` - implement amortization resolution with limits, diagnostics, identities, and fingerprints; `src/cadrumo/application/aggregation/_amortization.py`.
- [ ] `W03.P11.S64` - enroll amortization resolver ownership and source dispositions; `src/cadrumo/application/aggregation/_source_mesh.py`.
- [ ] `W03.P11.S65` - supply encrypted asset and finca repositories through calculation orchestration; `src/cadrumo/application/modelo/_calculation_actions.py`.
- [ ] `W03.P11.S66` - add grounded amortization bindings and casilla linkage for supported revisions; `src/cadrumo/_data/registry/aeat/modelos/100/revisions`.
- [ ] `W03.P11.S67` - prove amortization source ownership and ledger-expense collision behavior; `src/cadrumo/application/modelo/tests/test_amortization_source_mesh.py`.
- [ ] `W03.P11.S68` - prove the real encrypted amortization calculation-revision round trip and anti-tautology mutation; `src/cadrumo/adapters/persistence/profile/tests/test_amortization_source_revision_roundtrip.py`.
- [ ] `W03.P11.S69` - prove the operator calculation, replay, review, and supported export path; `src/cadrumo/entrypoints/cli/tests/test_amortization_modelo_workflow.py`.
- [ ] `W03.P11.S70` - promote each proven amortization candidate to connected and close rejected duplicates honestly; `src/cadrumo/_data/source_connectivity/census.toml`.
- [ ] `W03.P11.S71` - conduct a formal code review of the amortization vertical slice; `.vault/audit/2026-08-22-amortization-casilla-connection-code-review.md`.

## Wave `W04` - resolve remaining typed-domain candidates

Resolve the remaining secure-domain candidates after inventory and amortization, with fincas and non-amortization asset facts kept separate.

### Phase `W04.P12` - adjudicate and deliver finca facts

Resolve the finca-to-filing mapping and deliver only the officially supported facts.

- [ ] `W04.P12.S72` - ground per-finca M100 destination semantics and revision coverage; `.vault/research/2026-08-22-finca-casilla-grounding-research.md`.
- [ ] `W04.P12.S73` - decide contract, property, activity, attribution, and annual aggregation grain; `.vault/adr/2026-08-22-finca-casilla-mapping-adr.md`.
- [ ] `W04.P12.S74` - implement the adjudicated finca taxonomy, selectors, and resolver; `src/cadrumo/application/aggregation/_fincas.py`.
- [ ] `W04.P12.S75` - add grounded finca bindings and casilla linkage for supported revisions; `src/cadrumo/_data/registry/aeat/modelos/100/revisions`.
- [ ] `W04.P12.S76` - prove finca diagnostics, provenance, ownership, encrypted revision persistence, and replay; `src/cadrumo/application/modelo/tests/test_finca_source_mesh.py`.
- [ ] `W04.P12.S77` - prove the operator review and supported export path for finca-derived values; `src/cadrumo/entrypoints/cli/tests/test_finca_modelo_workflow.py`.
- [ ] `W04.P12.S78` - close the finca census disposition from production evidence; `src/cadrumo/_data/source_connectivity/census.toml`.
- [ ] `W04.P12.S79` - conduct a formal code review of the finca vertical slice; `.vault/audit/2026-08-22-finca-casilla-connection-code-review.md`.

### Phase `W04.P13` - adjudicate and deliver non-amortization asset facts

Resolve every remaining asset-domain filing candidate independently from amortization.

- [ ] `W04.P13.S80` - ground filing destinations for non-amortization facts held by the asset repository; `.vault/research/2026-08-22-assets-casilla-grounding-research.md`.
- [ ] `W04.P13.S81` - decide which asset facts are connectable, manual by design, duplicate, or not applicable; `.vault/adr/2026-08-22-assets-casilla-mapping-adr.md`.
- [ ] `W04.P13.S82` - implement every adjudicated asset selector and resolver channel; `src/cadrumo/application/aggregation/_assets.py`.
- [ ] `W04.P13.S83` - add grounded asset bindings and destination linkage for supported revisions; `src/cadrumo/_data/registry/aeat/modelos`.
- [ ] `W04.P13.S84` - prove asset ownership, diagnostics, provenance, encrypted round trip, replay, review, and supported export; `src/cadrumo/application/modelo/tests/test_asset_source_mesh.py`.
- [ ] `W04.P13.S85` - close every asset candidate with its proven disposition; `src/cadrumo/_data/source_connectivity/census.toml`.
- [ ] `W04.P13.S86` - conduct a formal code review of the asset vertical slice; `.vault/audit/2026-08-22-assets-casilla-connection-code-review.md`.

## Wave `W05` - connect or close every deferred row source

Treat each existing deferred row source as its own vertical slice; shared worksheet ingress may be refactored once, but legal semantics, resolver ownership, persistence proof, and census closure remain independent.

### Phase `W05.P14` - establish durable row-observation ingress

Carry assembled typed worksheet rows across the governed calculation and encrypted revision boundary.

- [ ] `W05.P14.S87` - define the application command that accepts assembled typed row observations for calculation; `src/cadrumo/application/calculations/_row_set_assembly.py`.
- [ ] `W05.P14.S88` - route Google Sheets pull output into the governed calculation input boundary; `src/cadrumo/entrypoints/cli/_config/_google_sync_calc.py`.
- [ ] `W05.P14.S89` - preserve grouping, row index, binding identity, source identity, and fingerprint through ingress; `src/cadrumo/domain/modelos/_calculation_revision.py`.
- [ ] `W05.P14.S90` - reject unknown fields, row ownership collisions, sparse invalid rows, and caller substitution; `src/cadrumo/application/storage/calc_sheets/_row_set_assembly.py`.
- [ ] `W05.P14.S91` - prove a real worksheet export-pull-calculate encrypted revision round trip; `src/cadrumo/application/storage/calc_sheets/tests/test_row_set_calculation_roundtrip.py`.

### Phase `W05.P15` - resolve M232 related-party operations

Adjudicate, connect or close, persist, and review the M232 row source.

- [ ] `W05.P15.S92` - adjudicate M232 row semantics and source ownership from official evidence; `.vault/research/2026-08-22-m232-row-source-grounding-research.md`.
- [ ] `W05.P15.S93` - enroll the related-party operation resolver and remove its deferral; `src/cadrumo/application/aggregation/_source_mesh.py`.
- [ ] `W05.P15.S94` - prove row persistence, diagnostics, provenance, replay, review, and export for M232; `src/cadrumo/application/modelo/tests/test_m232_row_source.py`.
- [ ] `W05.P15.S95` - close the M232 census disposition and obtain formal review; `.vault/audit/2026-08-22-m232-row-source-code-review.md`.

### Phase `W05.P16` - resolve M360 refund operations

Adjudicate, connect or close, persist, and review the M360 row source.

- [ ] `W05.P16.S96` - adjudicate M360 row semantics and source ownership from official evidence; `.vault/research/2026-08-22-m360-row-source-grounding-research.md`.
- [ ] `W05.P16.S97` - enroll the refund-operation resolver and remove its deferral; `src/cadrumo/application/aggregation/_source_mesh.py`.
- [ ] `W05.P16.S98` - prove row persistence, diagnostics, provenance, replay, review, and export for M360; `src/cadrumo/application/modelo/tests/test_m360_row_source.py`.
- [ ] `W05.P16.S99` - close the M360 census disposition and obtain formal review; `.vault/audit/2026-08-22-m360-row-source-code-review.md`.

### Phase `W05.P17` - resolve M182 donor rows

Adjudicate, connect or close, persist, and review the M182 row source.

- [ ] `W05.P17.S100` - adjudicate M182 donor-row semantics and source ownership from official evidence; `.vault/research/2026-08-22-m182-row-source-grounding-research.md`.
- [ ] `W05.P17.S101` - enroll the donor resolver and remove its deferral; `src/cadrumo/application/aggregation/_source_mesh.py`.
- [ ] `W05.P17.S102` - prove row persistence, diagnostics, provenance, replay, review, and export for M182; `src/cadrumo/application/modelo/tests/test_m182_row_source.py`.
- [ ] `W05.P17.S103` - close the M182 census disposition and obtain formal review; `.vault/audit/2026-08-22-m182-row-source-code-review.md`.

### Phase `W05.P18` - resolve M193 contributor-expense rows

Adjudicate, connect or close, persist, and review the M193 row source.

- [ ] `W05.P18.S104` - adjudicate M193 contributor-expense semantics and source ownership from official evidence; `.vault/research/2026-08-22-m193-row-source-grounding-research.md`.
- [ ] `W05.P18.S105` - enroll the contributor-expense resolver and remove its deferral; `src/cadrumo/application/aggregation/_source_mesh.py`.
- [ ] `W05.P18.S106` - prove row persistence, diagnostics, provenance, replay, review, and export for M193; `src/cadrumo/application/modelo/tests/test_m193_row_source.py`.
- [ ] `W05.P18.S107` - close the M193 census disposition and obtain formal review; `.vault/audit/2026-08-22-m193-row-source-code-review.md`.

### Phase `W05.P19` - resolve M296 withholding rows

Adjudicate, connect or close, persist, and review the M296 row source.

- [ ] `W05.P19.S108` - adjudicate M296 withholding-row semantics and source ownership from official evidence; `.vault/research/2026-08-22-m296-row-source-grounding-research.md`.
- [ ] `W05.P19.S109` - enroll the M296 withholding resolver and remove its deferral; `src/cadrumo/application/aggregation/_source_mesh.py`.
- [ ] `W05.P19.S110` - prove row persistence, diagnostics, provenance, replay, review, and export for M296; `src/cadrumo/application/modelo/tests/test_m296_row_source.py`.
- [ ] `W05.P19.S111` - close the M296 census disposition and obtain formal review; `.vault/audit/2026-08-22-m296-row-source-code-review.md`.

## Wave `W06` - rerun discovery, align documentation, and close honestly

Repeat the census after every delivered capability, process newly exposed candidates through bounded adjudication, align shipped documentation, and prove that no candidate remains unclassified, expired, silently deferred, or unactioned.

### Phase `W06.P20` - run the recurring discovery-and-delivery loop

Repeat discovery and bounded delivery until the census reaches a stable, fully actioned state.

- [ ] `W06.P20.S112` - regenerate the connectivity census after all planned source slices; `src/cadrumo/_data/source_connectivity/census.toml`.
- [ ] `W06.P20.S113` - create bounded research and decision records for every newly discovered connect candidate; `.vault/research`.
- [ ] `W06.P20.S114` - deliver every newly adjudicated connection through the canonical vertical-slice contract; `src/cadrumo/application/aggregation`.
- [ ] `W06.P20.S115` - classify every rejected or blocked candidate with evidence, owner, review condition, and bounded follow-up; `src/cadrumo/_data/source_connectivity/census.toml`.
- [ ] `W06.P20.S116` - rerun discovery until two consecutive runs produce no unclassified or unactioned candidate; `.vault/audit/2026-08-22-source-casilla-connectivity-close-audit.md`.
- [ ] `W06.P20.S117` - prove the final census has no expired deferral, unexplained disappearance, or unsupported connected claim; `dev/source_connectivity/tests/test_campaign_close.py`.

### Phase `W06.P21` - synchronize operator and developer documentation

Apply the approved documentation wireframe to the shipped architectural and operator surfaces.

- [ ] `W06.P21.S118` - explain registry authority, projections, secure aggregates, bindings, and calculation revisions; `docs/architecture/index.md`.
- [ ] `W06.P21.S119` - document typed selectors, source ownership, scalar values, and row-indexed bindings; `docs/reference/registry-legal-api.md`.
- [ ] `W06.P21.S120` - document worksheet ingress, evidence, persistence, and non-attachment semantics; `docs/reference/import-export-and-evidence.md`.
- [ ] `W06.P21.S121` - explain source resolution, provenance, manual fallbacks, and connected-domain boundaries; `docs/explanation/how-renta-is-assembled.md`.
- [ ] `W06.P21.S122` - document the inventory, amortization, finca, and asset operator workflow for M100; `docs/how-to/modelo-100.md`.
- [ ] `W06.P21.S123` - document inspection of scalar, row, source identity, fingerprint, and diagnostic values; `docs/how-to/review-calculation-values.md`.
- [ ] `W06.P21.S124` - update sequence contracts for every changed documented command; `docs/_sequences/contracts`.
- [ ] `W06.P21.S125` - complete technical review against live CLI and calculation behavior; `.vault/audit/2026-08-22-source-casilla-documentation-technical-review.md`.
- [ ] `W06.P21.S126` - complete editorial review for newcomer clarity, terminology, and link integrity; `.vault/audit/2026-08-22-source-casilla-documentation-editorial-review.md`.
- [ ] `W06.P21.S127` - pass documented-command conformance and the nitpicky documentation build; `dev/docs/tests/test_docs_build.py`.

### Phase `W06.P22` - complete campaign verification and review

Prove every campaign requirement against current artifacts, gates, execution records, and formal review.

- [ ] `W06.P22.S128` - run focused registry, source-mesh, secure-roundtrip, CLI, replay, review, and export gates; `src/cadrumo`.
- [ ] `W06.P22.S129` - run the feature-surface quality gate for every campaign-owned file; `.vault/exec/2026-08-22-source-casilla-integration`.
- [ ] `W06.P22.S130` - run the full connectivity census and ratchet against the final tree; `dev/source_connectivity/check.py`.
- [ ] `W06.P22.S131` - reconcile every plan Step with its execution record and phase summary; `.vault/exec/2026-08-22-source-casilla-integration`.
- [ ] `W06.P22.S132` - conduct the final formal safety, intent, architecture, and quality review; `.vault/audit/2026-08-22-source-casilla-integration-final-code-review.md`.
- [ ] `W06.P22.S133` - record requirement-by-requirement campaign completion evidence with zero unresolved census rows; `.vault/audit/2026-08-22-source-casilla-connectivity-close-audit.md`.

## Parallelization

Waves are hard-sequenced. W01 must land before any source is classified as connected. Inventory in W02 must finish before amortization in W03 begins. W03 must finish before remaining candidates in W04 and W05.

Within W01, registry-side and source-capability derivation may proceed in parallel after P01, but publication and ratchet enforcement wait for both. Within each source Wave, implementation cannot start before official adjudication closes. Registry declarations, resolver implementation, and tests may proceed in parallel only after the decision fixes selector shape, target semantics, grain, and override policy.

The five row-source Phases in W05 may execute in parallel after durable row ingress in P14 lands, because each retains separate grounding, resolver ownership, proof, census closure, and review. Documentation context gathering may run alongside late implementation, but final wording and technical review wait for the production behavior. W06 closes only after all earlier Waves and every newly discovered bounded slice are complete.
## Verification

The plan is complete only when:

- The canonical census accounts for every validated registry destination candidate, declared source kind, secure typed repository, supported ingress, row assembler, exported helper, and readiness declaration.
- The ratchet fails for unclassified capability, unexplained disappearance, expired blocked state, missing ownership or follow-up, and unsupported connected claims.
- Inventory is officially adjudicated first and amortization second; neither is mechanically mapped from lexical similarity or obsolete numeric casilla wording.
- Every production connection uses canonical `BindingSourceKind`, typed selector validation, registry bindings, enrolled resolver ownership, explicit precedence and override policy, diagnostics, source identity, fingerprint provenance, and legal/source-reference parity.
- Every connected source passes a real encrypted `CalculationRevision` strict round trip and an anti-tautology boundary mutation.
- Every connected source passes operator-path anti-dormancy, collision, replay, review, and supported export checks.
- Every candidate ends as `connected`, `manual_by_design`, `not_applicable`, `duplicate_or_stale`, `grounding_blocked`, `ingress_blocked`, or `registry_blocked`, with all blocked states owned and linked to bounded follow-up.
- Two consecutive final discovery runs expose no unclassified, expired, silently deferred, or unactioned candidate.
- All approved operator and developer documentation agrees with the live architecture and passes command-conformance and nitpicky Sphinx gates.
- Every Phase has an execution summary, every Step has an execution record, every formal code review passes, and all plan rows are checked.
