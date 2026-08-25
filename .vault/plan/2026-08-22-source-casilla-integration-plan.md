---
tags:
  - '#plan'
  - '#source-casilla-integration'
date: '2026-08-22'
modified: '2026-08-25'
body_hash: 'sha256:ca3742e2606b07c7997c0c639f27ffe1ee772e4cf0281f3bdcc3ddb3493bb151'
tier: L3
related:
  - '[[2026-08-22-source-casilla-integration-adr]]'
  - '[[2026-08-22-source-casilla-integration-research]]'
  - '[[2026-08-22-source-casilla-integration-m182-row-source-grounding-research]]'
  - '[[2026-08-22-modelo-work-binding-architecture-inventory-gap-verification-reference]]'
  - '[[2026-08-23-inventory-casilla-mapping-adr]]'
  - '[[2026-08-23-amortization-casilla-mapping-adr]]'
  - '[[2026-08-23-inventory-casilla-grounding-research]]'
  - '[[2026-08-23-amortization-casilla-grounding-research]]'
---

<!-- RETIRED: S52, S191, S193 -->

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
- [x] `W01.P05.S28` - prove each ratchet failure mode bites under an external mutation; `dev/source_connectivity/tests/test_check.py`.
- [x] `W01.P05.S29` - enroll the connectivity check in the repository quality-gate surface; `pyproject.toml`.
- [x] `W01.P05.S30` - conduct a formal code review of the census and ratchet foundation; `.vault/audit/2026-08-22-source-casilla-integration-census-code-review.md`.

### Phase `W01.P23` - remediate census review findings

Close the formal review findings before any source candidate is promoted or inventory behavior changes.

- [x] `W01.P23.S156` - replace advisory destination strings with typed registry-resolvable candidate identities and fail on absent or ambiguous destinations; `src/cadrumo/application/registry/source_connectivity.py`.
- [x] `W01.P23.S157` - verify every reviewed capability locator remains re-fetchable and corresponds to its stable capability identity; `dev/source_connectivity/check.py`.
- [x] `W01.P23.S158` - emit deterministic per-capability census membership and reviewed disposition evidence for aggregate coverage buckets; `dev/source_connectivity/cli.py`.
- [x] `W01.P23.S159` - make the census and ratchet modules clean on their intended static type-check surface; `dev/source_connectivity`.
- [x] `W01.P23.S160` - decide and implement the canonical live connected-proof gate composition; `src/cadrumo/application/registry`.
- [x] `W01.P23.S161` - re-review the remediated census foundation and close every recorded finding; `.vault/audit/2026-08-22-source-casilla-integration-census-code-review-audit.md`.
- [x] `W01.P23.S162` - extend ingress discovery across canonical command-spec declarations and adjudicate the resulting census drift; `dev/source_connectivity/discovery.py`.
- [x] `W01.P23.S225` - Adjudicate Modelo 036's exact event-driven profile source as manual-by-design and retain the human-filed no-local-submission boundary; `src/cadrumo/application/registry/source_connectivity.py; src/cadrumo/_data/source_connectivity/census.toml; dev/source_connectivity/; .vault/reference/`.

## Wave `W02` - adjudicate and connect inventory first

Resolve the inventory tax mapping before changing production behavior, then deliver the complete canonical slice if and only if official evidence proves the mapping.

### Phase `W02.P06` - adjudicate inventory semantics

Settle revision coverage, source facts, sign, units, activity grain, absence semantics, and override ownership.

- [x] `W02.P06.S31` - ground M100 inventory increase, purchases, and decrease semantics against official AEAT and BOE sources; `.vault/research/2026-08-23-inventory-casilla-grounding-research.md`.
- [x] `W02.P06.S32` - adjudicate the mapping from opening stock, purchase movements, and closing stock to 0177, 0181, and 0182; `.vault/adr/2026-08-23-inventory-casilla-mapping-adr.md`.
- [x] `W02.P06.S33` - decide revision windows, activity aggregation, sign, rounding, missing-ledger behavior, and caller override policy; `.vault/adr/2026-08-23-inventory-casilla-mapping-adr.md`.
- [x] `W02.P06.S34` - remove or correct the stale Anexo D casilla 0155 intent after adjudication; `src/cadrumo/domain/contribuyente/inventory/__init__.py`.
- [x] `W02.P06.S35` - record the adjudicated inventory disposition and re-fetchable evidence; `src/cadrumo/_data/source_connectivity/census.toml`.

### Phase `W02.P07` - implement the inventory source contract

Add inventory to the canonical taxonomy and resolution mesh without bypassing secure domain ownership.

- [x] `W02.P07.S36` - add the inventory source kind to the canonical taxonomy; `src/cadrumo/core/aggregation.py`.
- [x] `W02.P07.S37` - define and validate the typed inventory selector contract; `src/cadrumo/domain/calculations/registry/_inventory_bindings.py`.
- [x] `W02.P07.S38` - enroll inventory selector validation in registry binding construction; `src/cadrumo/domain/calculations/registry/_bindings.py`.
- [x] `W02.P07.S163` - define validated complete inventory acquisition-cost facts including attributable costs, non-recoverable IVA, and evidence completeness; `src/cadrumo/domain/contribuyente/inventory`.
- [x] `W02.P07.S164` - propagate complete acquisition-cost facts through inventory application and operator ingress; `src/cadrumo/application/inventory; src/cadrumo/entrypoints/cli`.
- [x] `W02.P07.S165` - prove complete acquisition-cost fields survive the encrypted inventory repository round trip; `src/cadrumo/adapters/persistence/profile/tests/test_inventory_roundtrip.py`.
- [x] `W02.P07.S166` - replace bare closing-stock authority with a provenance-bearing physical-closing observation and prior-closing continuity contract; `src/cadrumo/domain/contribuyente/inventory`.
- [x] `W02.P07.S167` - propagate physical-closing authority and continuity evidence through secure inventory ingress; `src/cadrumo/application/inventory; src/cadrumo/entrypoints/cli`.
- [x] `W02.P07.S168` - produce the strict complete 0177, 0181, and 0182 inventory domain projection; `src/cadrumo/domain/contribuyente/inventory`.
- [x] `W02.P07.S169` - formally review the inventory source prerequisites before resolver implementation; `.vault/audit/2026-08-23-inventory-source-prerequisites-code-review.md`.
- [x] `W02.P07.S39` - implement inventory repository resolution, diagnostics, source identity, and fingerprint provenance; `src/cadrumo/application/aggregation/_inventory.py`.
- [x] `W02.P07.S40` - enroll the inventory resolver and explicit source disposition; `src/cadrumo/application/aggregation/_source_mesh.py`.
- [x] `W02.P07.S41` - supply the encrypted inventory repository through calculation orchestration; `src/cadrumo/application/modelo/_calculation_actions.py`.
- [x] `W02.P07.S42` - enforce inventory source ownership and caller-override refusal; `src/cadrumo/application/modelo/_calculate_input.py`.

### Phase `W02.P08` - bind inventory into the legal registry

Declare only the revision-specific facts established by adjudication.

- [x] `W02.P08.S170` - add typed row-source identity coordinates to the canonical source-resolution carrier and collision merge; `src/cadrumo/application/aggregation/_source_mesh.py`.
- [x] `W02.P08.S171` - persist typed row-source identity coordinates on encrypted CalculationRevision state; `src/cadrumo/domain/modelos/_calculation_revision.py`.
- [x] `W02.P08.S172` - define validated inventory operation row-template selectors without taxpayer activity identities; `src/cadrumo/domain/calculations/registry/_inventory_bindings.py`.
- [x] `W02.P08.S173` - carry typed row-source identity coordinates through ModeloBindingValue filing state; `src/cadrumo/domain/filing/_schema.py`.
- [x] `W02.P08.S174` - propagate row-source identities through calculation replay and review assembly; `src/cadrumo/application/modelo`.
- [x] `W02.P08.S175` - redact raw row-source identities while exposing safe cohort fingerprints in operator output; `src/cadrumo/entrypoints/cli`.
- [x] `W02.P08.S176` - enumerate canonical runtime inventory activities into deterministic atomic three-operation row cohorts; `src/cadrumo/application/aggregation/_inventory.py`.
- [x] `W02.P08.S43` - add grounded inventory operation row-template bindings for supported M100 revisions without taxpayer activity identities; `src/cadrumo/_data/registry/aeat/modelos/100/revisions`.
- [x] `W02.P08.S185` - ground which supported M100 filing formats carry repeated economic-activity casilla rows and their exact official coordinates; `.vault/research/2026-08-23-inventory-casilla-grounding-research.md`.
- [x] `W02.P08.S205` - amend this plan with one renderer step and one proof step per grounded row-capable format, or record no renderer when no supported format qualifies; `.vault/plan/2026-08-22-source-casilla-integration-plan.md`.
- [x] `W02.P08.S186` - add typed row-indexed casilla values and direct-materialization provenance to the canonical source-resolution carrier; `src/cadrumo/domain/calculations, src/cadrumo/application/aggregation/_source_mesh.py`.
- [x] `W02.P08.S187` - persist row-indexed casilla values and direct-materialization provenance through encrypted CalculationRevision state; `src/cadrumo/domain/modelos/_calculation_revision.py, src/cadrumo/application/modelo, src/cadrumo/adapters/persistence/storage/_namespace_registry.py, src/cadrumo/adapters/persistence/profile/tests/test_source_mesh_revision_roundtrip.py, src/cadrumo/core/tests/test_persisted_format_enrolment_binding.py`.
- [ ] `W02.P08.S188` - exclude ROWS bindings from scalar calculation-input projection; `src/cadrumo/application/modelo/_calculation_actions.py`.
- [ ] `W02.P08.S194` - exclude ROWS bindings from scalar formula operand resolution; `src/cadrumo/domain/calculations`.
- [ ] `W02.P08.S189` - exclude ROWS bindings from scalar draft bound-casilla discovery; `src/cadrumo/application/filing/__init__.py`.
- [ ] `W02.P08.S195` - exclude ROWS binding maps from scalar decimal-input coercion; `src/cadrumo/application/filing/__init__.py`.
- [ ] `W02.P08.S44` - link each inventory operation row template to its adjudicated M100 activity-row casilla; `src/cadrumo/_data/registry/aeat/modelos/100/revisions`.
- [ ] `W02.P08.S190` - materialize inventory binding rows bijectively into direct row-indexed casilla values; `src/cadrumo/application/modelo/_calculation_resolution.py`.
- [ ] `W02.P08.S217` - ground the canonical authority, lifecycle, and shared activity identity for the M100 direct-estimation activity envelope required by repeated XML rows; `.vault/research`.
- [ ] `W02.P08.S218` - amend the inventory mapping decision with the grounded activity-envelope owner, join invariants, and explicit no-fabrication boundary; `.vault/adr/2026-08-23-inventory-casilla-mapping-adr.md`.
- [ ] `W02.P08.S219` - expand this plan from the accepted activity-envelope decision without duplicating an existing semantic source capability; `.vault/plan/2026-08-22-source-casilla-integration-plan.md`.
- [ ] `W02.P08.S220` - materialize canonical M100 direct-estimation activity-envelope rows keyed by the same durable activity identity as inventory and reusing TipoActividad; `src/cadrumo/application/aggregation`.
- [ ] `W02.P08.S221` - prove the activity-envelope join refuses absent, mismatched, duplicate, reordered, and fabricated TACT or IAE claims; `src/cadrumo/application/aggregation/tests`.
- [ ] `W02.P08.S222` - render row-indexed inventory casillas into repeated M100 XML ActividadEstDirecta nodes joined to complete grounded activity envelopes; `src/cadrumo/application/filing/_export_xml_dictionary.py`.
- [ ] `W02.P08.S224` - extend the canonical XML parser and post-write verifier with typed row-casilla coordinates and strict missing, extra, duplicate, and reordered-row equality; `src/cadrumo/domain/calculations/registry/_export_parse.py, src/cadrumo/application/filing/_export.py`.
- [ ] `W02.P08.S223` - prove repeated M100 XML inventory rows preserve sibling identity and order, enforce the six-row bound, round-trip row coordinates, and validate against the official XSD; `src/cadrumo/application/filing/tests`.
- [ ] `W02.P08.S192` - prove positive row-casilla identity, cohort, direct-materialization provenance, and scalar-exclusion invariants; `src/cadrumo/application/modelo/tests/test_inventory_row_casilla_materialization.py`.
- [ ] `W02.P08.S196` - prove row-casilla materialization refuses a missing coordinate; `src/cadrumo/application/modelo/tests/test_inventory_row_casilla_materialization.py`.
- [ ] `W02.P08.S197` - prove row-casilla materialization refuses an orphaned coordinate; `src/cadrumo/application/modelo/tests/test_inventory_row_casilla_materialization.py`.
- [ ] `W02.P08.S198` - prove row-casilla materialization refuses a duplicate coordinate claim; `src/cadrumo/application/modelo/tests/test_inventory_row_casilla_materialization.py`.
- [ ] `W02.P08.S199` - prove row-casilla materialization refuses a substituted value; `src/cadrumo/application/modelo/tests/test_inventory_row_casilla_materialization.py`.
- [ ] `W02.P08.S206` - prove row-casilla materialization refuses a substituted source identity; `src/cadrumo/application/modelo/tests/test_inventory_row_casilla_materialization.py`.
- [ ] `W02.P08.S200` - prove row-casilla materialization refuses reordered activity cohorts; `src/cadrumo/application/modelo/tests/test_inventory_row_casilla_materialization.py`.
- [ ] `W02.P08.S201` - prove row-casilla materialization refuses cross-cohort fingerprint disagreement; `src/cadrumo/application/modelo/tests/test_inventory_row_casilla_materialization.py`.
- [ ] `W02.P08.S202` - prove ROWS binding maps cannot enter scalar decimal-input channels; `src/cadrumo/application/modelo/tests/test_inventory_row_casilla_materialization.py`.
- [ ] `W02.P08.S207` - prove ROWS binding maps cannot enter scalar formula channels; `src/cadrumo/application/modelo/tests/test_inventory_row_casilla_materialization.py`.
- [ ] `W02.P08.S203` - prove encrypted row-casilla state refuses a missing direct-materialization rule identity; `src/cadrumo/adapters/persistence/profile/tests/test_inventory_source_revision_roundtrip.py`.
- [ ] `W02.P08.S204` - prove encrypted row-casilla state refuses a substituted direct-materialization rule version; `src/cadrumo/adapters/persistence/profile/tests/test_inventory_source_revision_roundtrip.py`.
- [ ] `W02.P08.S209` - prove encrypted row-casilla state refuses a missing direct-materialization rule version; `src/cadrumo/adapters/persistence/profile/tests/test_inventory_source_revision_roundtrip.py`.
- [ ] `W02.P08.S211` - prove encrypted calculation revisions refuse missing row-casilla state; `src/cadrumo/adapters/persistence/profile/tests/test_inventory_source_revision_roundtrip.py`.
- [ ] `W02.P08.S212` - prove encrypted calculation revisions refuse orphaned row-casilla state; `src/cadrumo/adapters/persistence/profile/tests/test_inventory_source_revision_roundtrip.py`.
- [ ] `W02.P08.S213` - prove encrypted calculation revisions refuse duplicate row-casilla coordinates; `src/cadrumo/adapters/persistence/profile/tests/test_inventory_source_revision_roundtrip.py`.
- [ ] `W02.P08.S214` - prove encrypted calculation revisions refuse substituted row-casilla values; `src/cadrumo/adapters/persistence/profile/tests/test_inventory_source_revision_roundtrip.py`.
- [ ] `W02.P08.S215` - prove encrypted calculation revisions refuse reordered row-casilla activity cohorts; `src/cadrumo/adapters/persistence/profile/tests/test_inventory_source_revision_roundtrip.py`.
- [ ] `W02.P08.S216` - prove encrypted calculation revisions refuse cross-cohort row-casilla fingerprint disagreement; `src/cadrumo/adapters/persistence/profile/tests/test_inventory_source_revision_roundtrip.py`.
- [ ] `W02.P08.S210` - prove encrypted row-casilla state refuses a substituted direct-materialization rule identity; `src/cadrumo/adapters/persistence/profile/tests/test_inventory_source_revision_roundtrip.py`.
- [ ] `W02.P08.S45` - verify inventory template shape, legal grounding, runtime activity cohorts, typed row identities, and casilla linkage; `src/cadrumo/domain/calculations/registry/tests/test_inventory_bindings.py`.
- [ ] `W02.P08.S177` - prove runtime inventory row identity bijection, cohort equality, deterministic order, and atomic malformed-cohort refusal; `src/cadrumo/application/aggregation/tests/test_inventory_source.py`.

### Phase `W02.P09` - prove the inventory vertical slice

Prove the real encrypted and operator-facing path, including negative and conflict behavior.

- [ ] `W02.P09.S46` - prove inventory row-binding and row-casilla values plus direct-materialization provenance cross the real encrypted CalculationRevision boundary with strict equality; `src/cadrumo/adapters/persistence/profile/tests/test_inventory_source_revision_roundtrip.py`.
- [ ] `W02.P09.S47` - prove deleting persisted inventory row-source provenance is detected by the encrypted round-trip gate; `src/cadrumo/adapters/persistence/profile/tests/test_inventory_source_revision_roundtrip.py`.
- [ ] `W02.P09.S208` - prove deleting persisted inventory row-casilla provenance is detected by the encrypted round-trip gate; `src/cadrumo/adapters/persistence/profile/tests/test_inventory_source_revision_roundtrip.py`.
- [ ] `W02.P09.S178` - prove encrypted calculation revisions refuse a missing inventory row-source identity; `src/cadrumo/adapters/persistence/profile/tests/test_inventory_source_revision_roundtrip.py`.
- [ ] `W02.P09.S180` - prove encrypted calculation revisions refuse an orphaned inventory row-source identity; `src/cadrumo/adapters/persistence/profile/tests/test_inventory_source_revision_roundtrip.py`.
- [ ] `W02.P09.S181` - prove encrypted calculation revisions refuse duplicate inventory activity identity within one operation row set; `src/cadrumo/adapters/persistence/profile/tests/test_inventory_source_revision_roundtrip.py`.
- [ ] `W02.P09.S182` - prove encrypted calculation revisions refuse a substituted inventory row-source identity; `src/cadrumo/adapters/persistence/profile/tests/test_inventory_source_revision_roundtrip.py`.
- [ ] `W02.P09.S183` - prove encrypted calculation revisions refuse reordered inventory row-source identities; `src/cadrumo/adapters/persistence/profile/tests/test_inventory_source_revision_roundtrip.py`.
- [ ] `W02.P09.S48` - prove missing, incomplete, and unreadable inventory emit actionable diagnostics; `src/cadrumo/application/modelo/tests/test_inventory_source_mesh.py`.
- [ ] `W02.P09.S49` - prove caller values cannot collide with or replace inventory-owned values; `src/cadrumo/application/modelo/tests/test_inventory_source_mesh.py`.
- [ ] `W02.P09.S50` - prove the CLI create-to-calculate-to-review workflow reaches the inventory resolver; `src/cadrumo/entrypoints/cli/tests/test_inventory_modelo_workflow.py`.
- [ ] `W02.P09.S51` - prove recalculation and review preserve inventory row cohorts, row-casilla coordinates, source identities, fingerprints, and direct-materialization grounding; `src/cadrumo/application/modelo/tests/test_inventory_replay_review.py`.
- [ ] `W02.P09.S179` - prove replay and review preserve inventory activity cohorts and safe cohort fingerprints; `src/cadrumo/application/modelo/tests/test_inventory_replay_review.py`.
- [ ] `W02.P09.S184` - prove ordinary CLI output redacts raw inventory source-row identities; `src/cadrumo/entrypoints/cli/tests/test_output_surface_inventory.py`.
- [ ] `W02.P09.S53` - update inventory readiness to reflect only capabilities proven by the landed slice; `src/cadrumo/application/inventory/_source_readiness.py`.
- [ ] `W02.P09.S54` - promote inventory to connected only when a grounded row-capable format and every connected proof pass, otherwise record the evidence-backed blocked disposition with an owned follow-up; `src/cadrumo/_data/source_connectivity/census.toml`.
- [ ] `W02.P09.S55` - conduct a formal code review of the inventory vertical slice; `.vault/audit/2026-08-22-inventory-casilla-connection-code-review.md`.

## Wave `W03` - adjudicate and connect amortization second

Resolve whether the asset and finca amortization ledgers are authoritative filing sources or duplicate already-booked ledger expenses, then deliver every proven amortization connection.

### Phase `W03.P10` - adjudicate amortization semantics

Settle filing destination identity, substitutability, grain, precedence, absence semantics, rounding, and override policy.

- [x] `W03.P10.S56` - ground amortization destinations, revision windows, eligible basis, rates, limits, and asset grain; `.vault/research/2026-08-23-amortization-casilla-grounding-research.md`.
- [x] `W03.P10.S57` - determine whether asset amortization is a direct filing source or a duplicate of transaction-ledger expenses; `.vault/adr/2026-08-23-amortization-casilla-mapping-adr.md`.
- [x] `W03.P10.S58` - determine whether finca amortization shares or requires a distinct source contract; `.vault/adr/2026-08-23-amortization-casilla-mapping-adr.md`.
- [x] `W03.P10.S59` - decide grain, precedence, absence semantics, rounding, and override policy; `.vault/adr/2026-08-23-amortization-casilla-mapping-adr.md`.
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

- [x] `W05.P14.S87` - define the application command that accepts assembled typed row observations for calculation; `src/cadrumo/application/calculations/_row_set_assembly.py`.
- [x] `W05.P14.S88` - route Google Sheets pull output into the governed calculation input boundary; `src/cadrumo/entrypoints/cli/_config/_google_sync_calc.py`.
- [x] `W05.P14.S89` - preserve grouping, row index, binding identity, source identity, and fingerprint through ingress; `src/cadrumo/domain/modelos/_calculation_revision.py`.
- [x] `W05.P14.S90` - reject unknown fields, row ownership collisions, sparse invalid rows, and caller substitution; `src/cadrumo/application/storage/calc_sheets/_row_set_assembly.py`.
- [x] `W05.P14.S91` - prove a real worksheet export-pull-calculate encrypted revision round trip; `src/cadrumo/application/storage/calc_sheets/tests/test_row_set_calculation_roundtrip.py`.

### Phase `W05.P15` - resolve M232 related-party operations

Adjudicate, connect or close, persist, and review the M232 row source.

- [x] `W05.P15.S92` - adjudicate M232 row semantics and source ownership from official evidence; `.vault/research/2026-08-22-source-casilla-integration-m232-row-source-grounding-research.md`.
- [x] `W05.P15.S93` - retain the M232 related-party-operation deferral until its carrier preserves direction and relationship type, a secure source owner exists, and S94 proves the full encrypted row route; `src/cadrumo/_data/source_connectivity/census.toml`.
- [x] `W05.P15.S94` - prove the M232 related-party source remains refused at calculation ingress and unavailable to encrypted persistence/replay, diagnostics/review, and repeated-record export until the S93 reopening predicate is satisfied; `src/cadrumo/application/modelo/tests/test_deferred_detalle_source_advisories.py; dev/source_connectivity/tests/test_m232_deferral.py`.
- [x] `W05.P15.S95` - formally close the reviewed bounded M232 ingress-blocked census disposition and obtain final review; `.vault/audit/2026-08-25-source-casilla-integration-s95-m232-terminal-closure-review-audit.md`.

### Phase `W05.P16` - resolve M360 refund operations

Adjudicate, connect or close, persist, and review the M360 row source.

- [x] `W05.P16.S96` - adjudicate M360 row semantics and source ownership from official evidence; `.vault/research/2026-08-22-source-casilla-integration-m360-row-source-grounding-research.md`.
- [x] `W05.P16.S97` - retain the M360 refund-operation ingress-blocked census disposition and permit reopening only after one secure owner retains the full official request/document carrier with durable identity and fingerprint and S98 proves encrypted persistence/replay diagnostics/review and supported repeated-record export; `src/cadrumo/_data/source_connectivity/census.toml; dev/source_connectivity/tests/test_m360_deferral.py`.
- [x] `W05.P16.S98` - prove the M360 refund-operation source remains refused at calculation ingress and unavailable to a connected encrypted source lifecycle diagnostics/review and source-owned repeated-record export until the S97 reopening predicate is satisfied while separate manual M360 request bindings remain available; `dev/source_connectivity/tests/test_m360_deferral.py`.
- [x] `W05.P16.S99` - formally close the reviewed terminal M360 ingress-blocked census deferral, retain its owner, expiry, reopening predicate, and no-connected-route boundary, and obtain final review; `src/cadrumo/_data/source_connectivity/census.toml; dev/source_connectivity/tests/test_m360_deferral.py; .vault/audit/2026-08-25-source-casilla-integration-s99-m360-terminal-closure-review-audit.md`.

### Phase `W05.P17` - resolve Modelo 182 donor and declarant record facts

Adjudicate, connect or close, persist, and review donor-detail and Article-3
declarant facts without collapsing type-1 filer/header facts into type-2 donor
rows. Recipient entities, political-party cases, and protected-estate holders or
administrators remain separate filing-population limbs until official evidence
settles their source and record semantics.

- [x] `W05.P17.S100` - adjudicate Modelo 182 donor-detail and Article-3 declarant/header source semantics, including type-1 nature `3` and administrator-holder identity, from official evidence; `.vault/research/2026-08-22-source-casilla-integration-m182-row-source-grounding-research.md`.
- [ ] `W05.P17.S101` - enroll only the resolver paths that preserve the non-substitutable type-1 declarant/header and type-2 donor-detail facts, then remove their deferrals; `src/cadrumo/application/aggregation/_source_mesh.py`.
- [ ] `W05.P17.S102` - prove Modelo 182 declarant and donor-detail persistence, diagnostics, provenance, replay, review, and supported export without a lossy fold; `src/cadrumo/application/modelo/tests/test_m182_row_source.py`.
- [ ] `W05.P17.S103` - close the Modelo 182 census disposition and obtain formal review only after every accepted declarant and donor source path has proof; `.vault/audit/2026-08-22-m182-row-source-code-review.md`.

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
- [ ] `W06.P20.S226` - Adjudicate Modelo 187's non-substitutable payer and Article 42 RGAT entity/IIC value paths, including required type-1/type-2 filer facts, before defining a canonical source, binding, casilla, provenance, collision policy, or census disposition.; `.vault/research/; .vault/adr/; src/cadrumo/_data/source_connectivity/census.toml; src/cadrumo/_data/registry/aeat/modelos/187/`.
- [ ] `W06.P20.S227` - Adjudicate the Modelo 220 2024 and 2025 group-value origins, grain, source identity, provenance, and absence semantics before any m220 producer key, binding, casilla, or filing layout is introduced.; `.vault/research/; .vault/adr/; src/cadrumo/_data/source_connectivity/census.toml; src/cadrumo/_data/registry/aeat/modelos/220/`.
- [ ] `W06.P20.S228` - Adjudicate Modelo 390 2021's complete annual casilla and value-arrival surface, including the source facts and filing omissions beyond its parser-only boxes, before any source taxonomy, registry linkage, producer, or layout is authored.; `.vault/research/; .vault/adr/; src/cadrumo/_data/source_connectivity/census.toml; src/cadrumo/_data/registry/aeat/modelos/390/`.
- [ ] `W06.P20.S229` - Adjudicate Modelo 721's source facts, casillas, and value-arrival lifecycle separately for each exact structured-message contract era, without treating the XML/SOAP contract or export-plan S97-S99 as source evidence.; `.vault/research/; .vault/adr/; src/cadrumo/_data/source_connectivity/census.toml; src/cadrumo/_data/registry/aeat/modelos/721/`.
- [ ] `W06.P20.S230` - After Modelo 763's period-aware eras are selected, determine whether any non-header filing value has a distinct authoritative source lifecycle and add a candidate only when its fact, grain, and destination are evidenced.; `.vault/research/; src/cadrumo/_data/source_connectivity/census.toml; src/cadrumo/_data/registry/aeat/modelos/763/`.
- [ ] `W06.P20.S231` - Adjudicate Modelo 840 source and repeated-row value lifecycles independently from the generic CRLF transport bridge, then add only evidenced canonical bindings, provenance, and census dispositions without an M840-specific writer.; `.vault/research/; .vault/adr/; src/cadrumo/_data/source_connectivity/census.toml; src/cadrumo/_data/registry/aeat/modelos/840/`.
- [ ] `W06.P20.S232` - After Modelo 188's exact historic design eras are selected, determine whether any required external value lifecycle exists and add no source kind, binding, casilla, or census candidate until official fact-to-destination evidence settles it.; `.vault/research/; src/cadrumo/_data/source_connectivity/census.toml; src/cadrumo/_data/registry/aeat/modelos/188/`.
- [ ] `W06.P20.S233` - After Modelo 194's 2019-2024 source eras are selected, determine whether any required external value lifecycle exists and add no source kind, binding, casilla, or census candidate until official fact-to-destination evidence settles it.; `.vault/research/; src/cadrumo/_data/source_connectivity/census.toml; src/cadrumo/_data/registry/aeat/modelos/194/`.

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
