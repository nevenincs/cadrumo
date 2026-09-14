---
tags:
  - '#plan'
  - '#registry-authority-artifact-boundary'
date: '2026-09-14'
tier: L3
related:
  - '[[2026-09-14-registry-authority-artifact-boundary-indexed-storage-adr]]'
  - '[[2026-09-09-facts-registry-governed-fact-catalogue-adr]]'
  - '[[2026-09-14-registry-authority-artifact-boundary-indexed-storage-research]]'
  - '[[2026-09-14-registry-authority-artifact-boundary-indexed-storage-source-enrollment-reference]]'
  - '[[2026-09-14-registry-authority-artifact-boundary-indexed-storage-readiness-audit]]'
modified: '2026-09-14'
body_schema: body-v2
body_hash: 'sha256:87ecea071cfcb3b8033e7f59c46b7e0f669a97d3500ca14756386fe1e67d1311'
---

<!-- RETIRED: S03, S04, S05, S06, S08, S09, S10, S11, S12, S18, S25, S26, S29, S30, S31, S32, S33, S35, S36, S37, S38, S39, S40, S41, S43, S44, S45, S46, S48, S49, S51, S52, S53, S54, S55, S57, S58, S59, S60, S61, S62, S63, S64, S67, S68, S69, S70, S71, S72, S73, S75, S76, S77, S78, S79, S80, S81, S82, S83, S85, S86, S87, S88, S89, S90, S91, S94, S95, S96, S97, S98, S99, S100, S101, S102, S103, S104, S105, S107, S109, S111, S112, S113, S115, S116, S118, S119, S120, S121, S122, S123, S125, S128, S130, S133, S136, S137 -->

# Authority backend implementation plan

## Description

Replace the eager JSON authority with one indexed SQLite generation and typed loaders that retrieve and cache only requested components. Enroll the profile facts schema in the same captured compilation inputs. Keep canonical domain rules and full publication validation.

The route has three passes: build the complete compiler/store contract; migrate consumers through three parallel lanes; prove and publish the cutover. There are 40 cohesive work packages, not one task per edited file. The indexed-storage ADR governs all three waves; the amended facts-registry ADR additionally governs provider enrollment in P01. The related reference owns the inspected file inventory, and the readiness audit owns findings.

This is the implementation handoff. Every step remains open; execution stops at this plan boundary. Consolidated step identifiers retain gaps by design. New modules named below are planned insertion points, not claims that those files already exist.

## Steps

## Wave `W01` - Complete inputs and build the indexed candidate

Capture every authority source, repair enrollment gaps and build a fully validated SQLite candidate without changing the shipped runtime. The indexed-storage ADR governs the backend; the amended facts ADR governs provider ownership. Wave 2 depends on this candidate.

### Phase `W01.P01` - Capture all compilation inputs

Make profile schema and provider-owned declarations explicit captured inputs with strict parsing and coherent validation/cache identity.

- [x] `W01.P01.S01` - Introduce the explicit source set and expose profile-source selection through pipeline/cli.py; thread captured schema through compilation, validation, fingerprints and memo identities without ambient fallback; `dev/registry`.
- [x] `W01.P01.S02` - Implement strict captured-byte profile parsing and declared-reference validation, with focused missing-input, unknown-envelope and legal-reference defect fixtures; `dev/registry/compiler/profile_schema.py`.
- [x] `W01.P01.S07` - Make subtree ownership and dependency domains executable; reconcile nested fact census and family enrollment with focused defect fixtures; `dev/registry/compiler/fact_providers.py`.

### Phase `W01.P02` - Compile and verify the SQLite candidate

Define the format and build a complete independently verified database with source, component and generation identities.

- [x] `W01.P02.S13` - Define the component/codec contract and public typed query, generation-pin and profile create/decode context signatures, with representative fake behavior for the consumer lanes; `src/cadrumo/domain/calculations/registry/authority_artifact.py`.
- [x] `W01.P02.S14` - Implement the typed SQLite store and independent complete candidate reader, including read-only admission, full-file digest, manifest/global closure, structural checks and supported-library refusal; `src/cadrumo/domain/calculations/registry/authority_store.py`.
- [x] `W01.P02.S15` - Compile the complete source set into indexed SQLite components, including profile declarations, separately addressable layouts and evidence; `dev/registry/compiler/authority_database.py`.
- [x] `W01.P02.S17` - Implement complete candidate validation, exclusive content-addressed installation and atomic descriptor publication in an isolated staging destination, preserving prior state on failure; `dev/registry/pipeline/authority_publication.py`.
- [x] `W01.P02.S16` - Run checkpoint A once on representative source/enrollment and encoded-candidate fixtures; freeze lane contracts and preserve a runnable paired JSON baseline before retiring old APIs; `dev/registry/tests`.

## Wave `W02` - Replace eager runtime access

Implement generation-pinned typed loaders and migrate the enumerated profile, model, fact and evidence consumers in one coordinated integration branch. The indexed-storage ADR governs this wave. Wave 3 requires its complete API migration.

### Phase `W02.P03` - Implement typed on-demand authority access

Preserve canonical selection and bootstrap semantics while introducing component loaders, generation leases and bounded concurrent caches.

- [x] `W02.P03.S19` - Add operation/component identity checks, resource leases and at most four exclusive connection checkouts per reader; release before dependency decoding and distinguish cutover from corruption; `src/cadrumo/domain/calculations/registry/authority_store.py`.
- [x] `W02.P03.S20` - Implement accounted LRU retention and concurrent-load coalescing with oversize, failure, cycle and lease-retirement behavior; `src/cadrumo/domain/calculations/registry/authority_cache.py`.
- [x] `W02.P03.S21` - Expose generation-pinned typed access and replace eager public graph fields while preserving incarnation and stale-capture semantics; `src/cadrumo/domain/calculations/registry/authority.py`.
- [x] `W02.P03.S22` - Use complete revision metadata in the existing canonical selection rules without synthesising partial revision models; `src/cadrumo/domain/calculations/registry/temporal.py`.
- [x] `W02.P03.S23` - Resolve requested facts and preserve exact temporal, selector, precedence and provenance semantics without whole-catalogue hydration; `src/cadrumo/domain/calculations/registry/facts/resolution.py`.
- [x] `W02.P03.S24` - Replace whole-catalogue validation and snapshot construction in governed_fact_scope.py and snapshot.py with declared same-generation dependencies; refuse recursive bundled loading; `src/cadrumo/domain/calculations/registry`.

### Phase `W02.P04` - Pin profile schema through record and application flows

Remove raw schema reads and hidden record-validation lookups, preserving secure persistence and profile policies.

- [ ] `W02.P04.S27` - Define context-required profile create/decode factories and pure validators; preserve exact stored schema ID/version refusal without global I/O; `src/cadrumo/domain/user_profile/values.py`.
- [ ] `W02.P04.S28` - Thread the pinned schema through record lifecycle, secure repository decoding, projections, overview and validation; remove the duplicate schema cache; `src/cadrumo/application/user_profile`.
- [ ] `W02.P04.S34` - Pass schema context through profile custody and carry while preserving encrypted record and snapshot semantics; `src/cadrumo/adapters/persistence/storage`.
- [ ] `W02.P04.S42` - Migrate the enumerated profile-binding, readiness and advisory consumers to the pinned profile component under the profile-lane ownership list; `src/cadrumo/application/modelo`.
- [ ] `W02.P04.S47` - Migrate the listed auth, wizard, diagnostics and profile aggregation consumers plus domain/renta/maritime_exemption.py and dev/locales/_registry_scanner.py with their owning fixtures; `profile schema consumer migration`.
- [ ] `W02.P04.S50` - Migrate the enumerated profile CLI/TUI schema consumers and fixtures to compiled authority access; remove raw-loader references; `src/cadrumo/entrypoints`.

### Phase `W02.P05` - Migrate model and revision consumers

Replace eager model graph traversal with typed point lookup or explicit metadata iteration in each inventoried consumer.

- [ ] `W02.P05.S56` - Migrate the enumerated query, support, citation, lineage and revision consumers to point lookup or explicit metadata iteration under the model-lane ownership list; `src/cadrumo/domain/calculations/registry`.
- [ ] `W02.P05.S65` - Replace aggregation model scans with selected-context and explicit dependency inventories; `src/cadrumo/application/aggregation/service.py`.
- [ ] `W02.P05.S66` - Migrate calculation, carry, annual-summary, observation and cross-period consumers using the reviewed model-lane file inventory; `src/cadrumo/application/calculations`.
- [ ] `W02.P05.S74` - Migrate the enumerated model operation and persisted-revision consumers without taking profile-lane files; `src/cadrumo/application/modelo`.
- [ ] `W02.P05.S84` - Migrate the inventoried live, overview/calendar_warnings.py, foreign_asset_thresholds.py, spreadsheet CLI, domain/portals/registry.py and domain/transactions/m210_income_classification.py consumers; `model discovery consumer migration`.

### Phase `W02.P06` - Migrate facts, catalogues and evidence consumers

Route catalogue and evidence access through selected generation components without expanding unrelated payloads.

- [ ] `W02.P06.S92` - Migrate IVA facts, vocabulary, catalogues and evidence to requested components while preserving dated resolution; `src/cadrumo/domain/iva`.
- [ ] `W02.P06.S93` - Migrate the listed category, deadline, authorisation and treaty consumers under the fact-lane ownership list; `src/cadrumo/domain`.
- [ ] `W02.P06.S106` - Use point legal evidence access and integrate with concurrent corpus changes without expanding unrelated payloads; `src/cadrumo/application/corpus_search/citation_lookup.py`.
- [ ] `W02.P06.S108` - Migrate application/modelo/_work_review_assembly.py and adapters/outbound/aeat/sede/declarations_observations.py to referenced evidence lookup; `work-review and Sede evidence consumers`.

### Phase `W02.P07` - Require filing coordinates and close retired imports

Fix default filing selection and remove displaced raw-loader/eager API surfaces with their owning test fixtures.

- [x] `W02.P07.S110` - Require draft filing coordinates in runtime, export and verification; use selected source/layout dependencies and preserve stale-draft refusal; `src/cadrumo/application/filing`.
- [ ] `W02.P07.S114` - Retire the raw runtime parser after source tooling and all inventoried consumer fixtures migrate; remove displaced eager APIs and forwarding paths; `src/cadrumo/domain/user_profile/loader.py`.
- [ ] `W02.P07.S117` - Run checkpoint B once on the integrated authority/profile/filing contract selection plus focused import, lint and type checks; repair only observed failures; `src/cadrumo`.

## Wave `W03` - Prove and publish the backend cutover

Prove semantic, concurrency, package and performance acceptance before replacing the shipped JSON backend. The indexed-storage ADR owns cutover targets and refusal semantics. This wave concludes implementation only after future execution approval.

### Phase `W03.P08` - Prove integrity, concurrency and installed isolation

Exercise real encoded generations, Windows readers, package boundaries and profile/model/evidence operations without authoring files.

- [x] `W03.P08.S124` - Implement shared acceptance cases for component laziness, cache accounting, generation changes and admission-versus-use refusal; run them at checkpoint C; `src/cadrumo/domain/calculations/registry/tests`.
- [x] `W03.P08.S126` - Implement one publication acceptance suite for Windows held-reader cutover, database tamper, collisions and deferred cleanup; run it at checkpoint C; `dev/registry/tests/test_authority_generation_publication.py`.
- [x] `W03.P08.S127` - Switch package resource selection to one descriptor and its database; update archive gates and exclude every runtime authoring source and JSON fallback; `pyproject.toml`.
- [x] `W03.P08.S129` - Extend the single installed cohort with profile, fact, model, evidence and CLI/MCP isolation and refusal cases; `dev/packaging/tests/test_installed_oracles.py`.

### Phase `W03.P09` - Measure and complete the backend cutover

Apply paired performance gates, publish the single referenced SQLite generation and reconcile operational documentation and release gates.

- [x] `W03.P09.S131` - Extend the paired benchmark driver for independent workloads, full admission cost, incremental RSS and cache telemetry; run release measurements at checkpoint C; `dev/registry/benchmark_authority.py`.
- [ ] `W03.P09.S132` - Run checkpoint C once against isolated candidate publication: canonical compile/validation, final gates, one candidate installed cohort and paired benchmarks, reusing the exact artifact; `justfile`.
- [ ] `W03.P09.S134` - Promote the C-approved descriptor/database and retire shipped JSON; verify exact accepted bytes and package manifest without recompilation or another release suite; `src/cadrumo/_data/registry/authority`.
- [x] `W03.P09.S135` - Update how-to/publish-runtime-authority.md and reference/registry-legal-api.md from the final implementation and measured limitations; `docs`.

## Parallelization

The principal engineer owns architecture implementation: P01-P03, filing integration in P07, and final acceptance/cutover. S13 defines the typed store, query, generation-context and profile-context signatures and representative fake behavior; freeze them at checkpoint A. P03 and P04 implement those agreed contracts. Publish those signatures with representative fixtures so consumer lanes can start while the principal completes P03 internals. No lane needs a separate full compilation.

| Lane | Owner | Work and handoff |
| --- | --- | --- |
| Core and integration | Principal | Captured inputs, compiler, format, store/cache, canonical resolvers, snapshot dependency narrowing and filing context. Integrates the three lane results. |
| Profile | Sol medium | P04 and its owning fixtures. Pass the same pinned schema through creation, secure decoding, projections and user interfaces. |
| Models and revisions | Sol medium | P05 and its owning fixtures. Replace eager traversal with selected revision access or explicit metadata iteration. |
| Facts and evidence | Sol medium | P06 and its owning fixtures. Preserve dated resolution and retrieve only requested catalogues/evidence. |
| Packaging and documentation | Sol low, when a slot is free | Bounded package exclusions, installed-oracle wiring and the existing guides in P08-P09. Principal retains publication and performance decisions. |

Use at most the principal plus three agents concurrently. Brief each lane once with its file ownership, frozen interfaces, relevant reference inventory and expected return: code, owning fixture updates and any concrete blocker. Agents are not alone in the tree and must preserve concurrent edits. The principal resolves cross-lane contracts; agents send interface needs rather than editing another lane's files. Do useful independent work instead of agent wait calls.

The reference's consumer inventory bounds directory-scoped steps. Ownership exceptions are explicit: profile owns `application/modelo/_required_binding_gate.py`, the four other listed profile/advisory files, `entrypoints/cli/common.py`, profile CLI/config files, `domain/user_profile/registry_contract.py`, `domain/renta/maritime_exemption.py`, profile-dependent aggregation files, and `dev/locales/_registry_scanner.py`. Models owns the remaining listed modelo consumers, spreadsheet CLI, portal/transaction consumers and aggregation service. Facts owns `_work_review_assembly.py`, the Sede observation consumer and `registry/convenio.py`. Core owns authority/store/cache/artifact, temporal and fact resolution, `governed_fact_scope.py`, `snapshot.py`, all filing files, and final raw-loader retirement. Shared schema changes go through the principal. These assignments override overlapping directory names in step scopes.

P04-P06 run independently against the agreed interfaces. The principal may implement contextful filing in parallel, but retires displaced APIs only after the lanes integrate. P08 acceptance-fixture and package preparation can start when the format is fixed and a slot becomes free; its final runs depend on integrated P03-P07. Prepare documentation alongside implementation and finalise it from measured results. No separate lane audit or repeated corpus census is required: refresh the inspected caller inventory once at entry, then search only for unresolved references or changed interfaces.

Planned new modules are `dev/registry/compiler/profile_schema.py`, `dev/registry/compiler/authority_database.py`, and `src/cadrumo/domain/calculations/registry/authority_store.py` / `authority_cache.py`. An explicit source-set type may live with compiler authority; use existing publication, benchmark and fixture modules where they already own the behavior.

## Verification

Use three shared checkpoints. Fixture authoring and focused debugging belong to each owning work package; they do not create an extra campaign of per-file test runs. Reuse current canonical gate entrypoints and the in-flight tooling work rather than building another gate framework.

| Checkpoint | When | One shared validation run |
| --- | --- | --- |
| A - input and format contract | End of P02 | Representative source/enrollment and encoded-candidate tests: missing profile input, strict envelope/reference refusal, source invalidation, recursive provider ownership and codec parity. Preserve the old JSON baseline runner plus exact captured public sources before retiring its APIs. No full production publication or installed build here. |
| B - integrated runtime contract | End of P07 | One focused selection covering typed loading, profile record context, domain resolution and historical filing; required import/lint/type checks over the integrated changes. Include migrated fixture regressions without running a separate full suite per lane. |
| C - cutover acceptance | End of P09 | One full canonical compile/independent validation of the stable integrated tree, one sealed installed cohort, the shared integrity/concurrency acceptance suite, required final repository gates and paired performance measurements. Reuse the exact candidate database and package cohort for every applicable check. |

P08 steps prepare acceptance cases; S131 prepares the paired measurement driver. Execute their release runs together at C. Build the candidate wheel and sdist-rebuilt wheel before installed checks; both must package the same verified generation. S17 and C publish only into an isolated candidate destination; package that candidate descriptor/database for the installed cohort. S134 alone switches the shipped descriptor and removes JSON, then checks exact bytes/digests and the package manifest against the accepted candidate without recompiling or repeating the release suite. The prior shipped artifact stays available until this candidate passes. Where the canonical tooling already covers a check, consume that result rather than invoking its underlying suite again.

The ADR owns correctness, refusal and quantitative performance acceptance. Record one result per independent workload; do not average away a failing model. Tests must distinguish admission integrity from on-demand typed validation and cover every component family. Preserve full publication validation even though runtime hydration is selective.

Rerun only checks invalidated by a failure, changed input or changed contract. A source/compiler change invalidates the candidate and requires a replacement full compilation; unchanged artifacts and receipts remain reusable. No routine repeated benchmark, full-suite run, audit document or ceremonial per-lane review is added. The principal performs one integrated review before cutover. Record outcomes through the existing execution workflow, without duplicating evidence across documents.

The known enrollment test contradiction is repaired with P01's recursive ownership contract and checked at A. Historical measurements are a baseline, not evidence that SQLite already meets the targets. Completion requires all 40 packages and C acceptance; no application implementation or release run is part of this planning session.
