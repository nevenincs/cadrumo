---
tags:
  - '#plan'
  - '#justfile-design'
date: '2026-09-11'
tier: L3
related:
  - '[[2026-09-11-justfile-design-adr]]'
  - '[[2026-09-11-justfile-design-research]]'
  - '[[2026-09-11-justfile-design-audit]]'
modified: '2026-09-11'
body_schema: body-v2
body_hash: 'sha256:2d5b09e3ab00fa8d068398c5d8273901d461640b18348280bfd7d0759840126c'
---

<!-- RETIRED: P07 -->

# `justfile-design` plan

Reconcile primitive `dev/` ownership first, then replace the public justfile taxonomy,
migrate every caller, and retire the superseded and RAG surfaces.

## Description

This plan executes the accepted justfile-design decision grounded by the related
research and ADR-corpus audit. W01 through W04 are four concurrent agent lanes with
disjoint semantic and justfile-section ownership: environment/code quality, registry,
tests/packaging/artifacts, and documentation/domain operations. W05 integrates those
surfaces, migrates callers, removes old aliases and the connected RAG surface, then
proves taxonomy, population, registry, and decision closure.

The plan preserves the existing determinism-based CI verdict constraint and immutable
runtime-authority boundary without re-deciding them. It introduces no legacy
compatibility layer: old names retire after identified callers move.

## Steps

## Wave `W01` - agent lane 1 - environment and code quality

Agent slot 1 owns environment convergence, diagnosis, cleanup, code-quality primitive deduplication, and the corresponding public setup, doctor, check, fix, audit, and report sections without editing registry, test, packaging, or documentation owners.

### Phase `W01.P01` - separate environment lifecycle ownership

Choose one environment convergence facade and separate optional setup, read-only diagnosis, and cleanup.

- [x] `W01.P01.S01` - Consolidate fresh-worktree planning and initialization behind the canonical setup facade; `dev/init`.
- [x] `W01.P01.S02` - Consolidate environment installation and optional workstation provisioning behind distinct setup operations; `dev/env`.
- [x] `W01.P01.S03` - Separate developer readiness probes from environment mutation; `dev/env`.
- [x] `W01.P01.S04` - Keep reclamation reporting and application isolated from setup and doctor ownership; `dev/env/clean.py`.
- [x] `W01.P01.S52` - Preserve repository tooling inside minimal setup while keeping workstation and browser provisioning optional; `dev/init`.
- [x] `W01.P01.S33` - Preserve clean preview and destructive application as an isolated non-aggregated pair; `justfile`.

### Phase `W01.P02` - deduplicate quality audit and report ownership

Give each code-quality primitive one semantic owner and separate blocking checks from advisory scanners and rendered reports.

- [x] `W01.P02.S05` - Extract one shared persistence write-path analysis core for blocking and diagnostic consumers; `dev/quality/write_path_coverage.py`.
- [x] `W01.P02.S06` - Narrow the quality suite to blocking code-quality verdicts; `dev/quality`.
- [x] `W01.P02.S07` - Narrow advisory composition to normalized non-blocking scanners; `dev/audit`.
- [x] `W01.P02.S08` - Separate code-health report composition from primitive advisory scanners; `dev/audit/report.py`.
- [x] `W01.P02.S09` - Move dependency vulnerability verdict ownership out of advisory composition; `dev/audit/dependency_audit.py`.

### Phase `W01.P05` - replace setup check fix and audit recipes

Install the stable posture contracts and subject aggregates for environment and code/repository verification.

- [x] `W01.P05.S21` - Replace bootstrap setup and doctor recipes with minimal convergence optional provisioning and read-only diagnosis; `justfile`.
- [x] `W01.P05.S22` - Replace flat static checks with code and repository subject aggregates; `justfile`.
- [x] `W01.P05.S23` - Restrict fix recipes to mechanical source repair and move non-documentation committed derivatives to explicit generation verbs; `justfile`.
- [x] `W01.P05.S24` - Replace verdict-ambiguous audit names with advisory audits blocking checks and explicit reports; `justfile`.
- [x] `W01.P05.S59` - Expose the exact approved setup and doctor recipe manifest; `justfile`.

## Wave `W02` - agent lane 2 - registry lifecycle

Agent slot 2 owns registry validity, currentness, authority currency, exact runtime loadability, publication mutations, regulatory validation, registry reports, and the registry section of the public command surface.

### Phase `W02.P03` - complete registry lifecycle ownership

Expose distinct validity, currentness, publication, status, and exact artifact-backed runtime-load primitives.

- [x] `W02.P03.S10` - Expose whole-registry validity as one fail-closed primitive; `dev/registry/conformance/cli.py`.
- [x] `W02.P03.S11` - Add an exact artifact-backed bundled-authority runtime-load verdict; `dev/registry/conformance`.
- [x] `W02.P03.S12` - Expose read-only registry status across validity targets authority publication and runtime loadability; `dev/registry/analysis`.
- [x] `W02.P03.S13` - Expose existing target-currentness authority-publication target-publication and digest-bound republish operations through distinct semantic entry points; `dev/registry/pipeline/cli.py`.
- [x] `W02.P03.S14` - Delegate the legacy render-check entry point to canonical target-currentness semantics pending caller migration; `dev/registry/pipeline/render_check.py`.
- [x] `W02.P03.S15` - Move regulatory-literal validation into the registry validation owner and delegate the former module during migration; `dev/registry/validation`.
- [x] `W02.P03.S16` - Move regulatory-embed validation into the registry validation owner and delegate the former module during migration; `dev/registry/validation`.
- [x] `W02.P03.S53` - Expose per-target generated-tree currentness as a read-only public primitive; `dev/registry/pipeline/cli.py`.
- [x] `W02.P03.S54` - Expose generated-tree and runtime-authority currency as delegated status facts without recomputation; `dev/registry/analysis/generated_tree_state.py`.
- [x] `W02.P03.S55` - Expose runtime-authority publication as a separately authorized mutation; `dev/registry/pipeline/authority_publication.py`.
- [x] `W02.P03.S56` - Expose target publication and digest-bound republishing as separately authorized mutations; `dev/registry/pipeline/_tree_publication.py`.

### Phase `W02.P06` - replace registry and test recipes

Expose the operator-question registry surface and subject-owned test populations with capability exclusions.

- [x] `W02.P06.S25` - Expose the ordered registry aggregate with validity before oracle bindings and runtime loadability; `justfile`.
- [x] `W02.P06.S60` - Expose registry generated-state and composite status reports separately from blocking checks; `justfile`.
- [x] `W02.P06.S61` - Expose registry authority publication target publication and republish mutations as separate recipes; `justfile`.
- [x] `W02.P06.S62` - Replace the generic modelo and registry-pipeline pass-throughs with authority-specific operations or demote them; `justfile`.

## Wave `W03` - agent lane 3 - tests packaging and artifacts

Agent slot 3 owns test-population assignment, private execution transport, packaging preflight and artifact campaigns, release builds, temporary cohorts, infrastructure images, and capability-qualified tests.

### Phase `W03.P04` - stabilize test and packaging ownership

Separate semantic test populations from execution transport and distinguish packaging deliverables, cohorts, and infrastructure.

- [x] `W03.P04.S17` - Keep lane execution timing continuation and report transport private and free of semantic membership; `dev/test_runs`.
- [x] `W03.P04.S18` - Inventory the heterogeneous developer-tooling population and record a canonical subject capability or temporary-backstop owner for each test; `dev/tests/test_lane_reachability.py`.
- [x] `W03.P04.S19` - Separate packaging preflight artifact campaign and temporary-cohort ownership; `dev/packaging`.
- [x] `W03.P04.S20` - Keep container capability probes outside portable product and release-artifact ownership; `dev/containers`.
- [x] `W03.P04.S57` - Reassign every tooling test population from the temporary backstop to a canonical subject or capability owner before closure; `dev`.
- [x] `W03.P04.S58` - Decide whether resident-service-marked tests are removed reclassified or explicitly outside public population accounting; `dev/docs`.

### Phase `W03.P12` - replace test packaging and artifact recipes

Expose subject-owned tests, packaging contracts and campaigns, release deliverables, temporary cohorts, infrastructure images, and capability-qualified operations.

- [x] `W03.P12.S26` - Replace test-all with product registry tooling packaging and capability-qualified aggregates; `justfile`.
- [x] `W03.P12.S27` - Make the pytest harness tooling-owned and a prerequisite of the canonical product test aggregate; `justfile`.
- [x] `W03.P12.S28` - Place the calculation cohort under registry-domain test ownership; `justfile`.
- [x] `W03.P12.S30` - Separate release distributions temporary packaging cohorts and infrastructure images; `justfile`.

## Wave `W04` - agent lane 4 - documentation and domain operations

Agent slot 4 owns the separate documentation namespace, contributor guidance, locale and TUI operations, database mutations, and truthful release preparation names.

### Phase `W04.P13` - replace documentation domain and release recipes

Install the separate posture-explicit documentation namespace and authority-specific locale TUI database and release preparation commands.

- [x] `W04.P13.S29` - Keep documentation under the exact posture-explicit docs manifest authorized by the ADR; `justfile`.
- [x] `W04.P13.S31` - Replace the generic locale pass-through with authority-consistent locale operations or demote it; `justfile`.
- [x] `W04.P13.S32` - Rename release readiness preview and rollback-plan recipes without adding release publication authority; `justfile`.
- [x] `W04.P13.S63` - Replace the generic TUI review and harness pass-throughs with authority-consistent operations or demote them; `justfile`.
- [x] `W04.P13.S64` - Replace database migration creation and upgrade with separately named mutation recipes; `justfile`.

## Wave `W05` - integrate migrate and retire

After all four agent lanes land, reconcile their disjoint justfile sections, migrate every tracked caller, retire legacy and RAG surfaces, and run cross-lane closure verification.

### Phase `W05.P14` - compose policy gates

Integrate the four lane-owned subject aggregates into explicit connected local and hosted-policy gate surfaces after their public names stabilize.

- [ ] `W05.P14.S73` - Declare gate-local network prerequisites and keep subject check aggregates portable; `justfile`.
- [ ] `W05.P14.S77` - Integrate the four independently edited justfile sections and resolve cross-section dependencies; `justfile`.
- [ ] `W05.P14.S75` - Compose the four lane-owned subject aggregates into the connected local gate with explicit exclusions; `justfile`.
- [ ] `W05.P14.S76` - Expose hosted per-push parity only after workflow membership is proven equal; `justfile`.

### Phase `W05.P08` - migrate automated callers

Move hosted workflows and hook configuration to subject aggregates and explicit policy gates.

- [ ] `W05.P08.S34` - Replace per-push recipe calls with the approved subject aggregates and gate contract; `.github/workflows/ci.yml`.
- [ ] `W05.P08.S35` - Replace dispatch-only recipe calls with explicit capability and artifact lanes; `.github/workflows/ci-full.yml`.
- [ ] `W05.P08.S36` - Update release and documentation workflow callers to truthful build deploy and release verbs; `.github/workflows`.
- [ ] `W05.P08.S37` - Keep pre-commit hooks verify-only while moving them to canonical leaf checks; `prek.toml`.
- [ ] `W05.P08.S65` - Inventory every tracked caller of current recipe names before any alias removal; `repository`.

### Phase `W05.P09` - migrate contributor documentation

Teach the new command vocabulary, registry lifecycle questions, capability exclusions, and destructive boundaries.

- [ ] `W05.P09.S38` - Replace contributor command guidance with the operator-intent taxonomy and explicit exclusions; `README.md`.
- [ ] `W05.P09.S39` - Document release build preview readiness and publication authority under the truthful names; `RELEASING.md`.
- [ ] `W05.P09.S40` - Document code registry repository test packaging and capability lanes without restating their implementations; `docs`.
- [ ] `W05.P09.S41` - Document the registry valid current published and loadable operator workflow; `docs`.

### Phase `W05.P10` - remove old and RAG surfaces

Delete superseded aliases, generic pass-throughs, duplicate owners, and the complete connected RAG justfile cluster.

- [ ] `W05.P10.S66` - Prove no tracked workflow hook script test configuration or document references a retired recipe before deleting aliases; `repository`.
- [ ] `W05.P10.S42` - Remove superseded bootstrap check test audit build release and dev-prefixed aliases after callers migrate; `justfile`.
- [ ] `W05.P10.S43` - Remove all RAG service indexing status and search recipes without replacement; `justfile`.
- [ ] `W05.P10.S44` - Remove the ignored RAG probe semantic check resident-service test and resident terminology sweep; `justfile`.
- [ ] `W05.P10.S45` - Remove or delegate duplicate write-path analysis implementations after the shared owner lands; `dev/audit/write_path_coverage.py`.
- [ ] `W05.P10.S46` - Remove obsolete registry render-check entry points after target-current callers migrate; `dev/registry/pipeline/render_check.py`.

### Phase `W05.P11` - verify command and decision closure

Prove recipe taxonomy, caller reachability, registry lifecycle claims, aggregate exclusions, and Vaultspec corpus consistency.

- [ ] `W05.P11.S47` - Extend recipe-contract mutation proofs for the new subject and authority boundaries; `dev/ci/prove_check_set_guards.py`.
- [ ] `W05.P11.S48` - Prove every tracked test population has exactly one canonical subject or capability owner and the temporary backstop is empty; `dev/tests/test_lane_reachability.py`.
- [ ] `W05.P11.S49` - Prove packaging preflight artifact and campaign selectors remain disjoint and complete; `dev/packaging/tests/test_preflight_recipe_selection.py`.
- [ ] `W05.P11.S50` - Prove registry validity currentness publication status and runtime-load commands exercise distinct owners; `dev/registry/tests`.
- [ ] `W05.P11.S51` - Validate the final Vaultspec graph supersession and lifecycle-document boundaries; `.vault`.
- [ ] `W05.P11.S67` - Prove the public recipe listing exactly matches the ADR manifest and contains no legacy or RAG aliases; `dev/ci`.
- [ ] `W05.P11.S68` - Prove setup doctor checks and reports satisfy their read-only or mutation contracts; `dev/ci`.
- [ ] `W05.P11.S69` - Prove portable gates exclude destructive outward live capability-dependent and temporary-fixture operations; `dev/ci`.
- [ ] `W05.P11.S70` - Prove release recipes cannot publish or execute rollback; `dev/release/tests`.
- [ ] `W05.P11.S71` - Prove installed-artifact tests consume the intended built cohort rather than stale scratch; `dev/packaging/tests`.
- [ ] `W05.P11.S72` - Prove advisory aggregates normalize scanner finding exits to non-blocking results; `dev/audit/tests`.
- [ ] `W05.P11.S74` - Prove unavailable dependency-advisory data fails the connected local gate without contaminating portable subject checks; `dev/audit/tests`.

## Parallelization

W01, W02, W03, and W04 are intentionally parallel and map one-to-one to four agent
slots. Each lane owns its named implementation packages and a disjoint region of the
`justfile`; no lane edits another lane's recipe section. W05 begins only after all four
lanes have delivered their replacement primitives and public sections.

Inside W01, S05 precedes S45. Inside W02, S10, S11, S13, S53, S55, and S56 precede S12
and S54; S13 precedes S14 and S46. Inside W03, population inventory precedes final
subject assignment. W04 documentation and domain-operation phases may proceed in
parallel where their files do not overlap.

In W05, S65 precedes named caller migrations. The justfile integration step precedes
gate composition. S66 then proves caller absence before S42-S46 remove legacy surfaces;
the justfile removals S42-S44 are serialized, while implementation removals S45-S46 may
proceed independently. P11 follows every removal.

## Verification

- Every public recipe has one documented posture and subject; no `dev-*`, ambiguous
  `*-all`, unqualified `ci`, or mixed-authority pass-through remains.
- `setup` is minimal; optional workstation and browser provisioning are explicit;
  doctor commands are read-only.
- Code, registry, repository, product-test, registry-test, tooling-test, packaging,
  release-build, temporary-cohort, and infrastructure-image boundaries are independently
  invocable and have no accidental cross-category membership.
- Documentation remains discoverable under `docs-*`, with checking, generation, build,
  serve, report, provision, and publish authority explicit.
- Registry commands independently prove validity, target currentness, authority
  publication currency, and exact artifact-backed runtime loadability; publication
  commands mutate only the named product.
- `check-registry` runs validity before oracle bindings, and registry status delegates
  to the validity, currentness, authority-currency, and runtime-load owners rather than
  recomputing their facts.
- Advisory audit aggregates do not fail on findings; blocking verdicts use `check-*`;
  reports state their exit posture.
- The pytest harness protects the product aggregate while remaining tooling-owned, and
  every test population has one canonical subject or capability owner.
- Release builds contain only published deliverables; temporary cohorts and
  infrastructure images remain separate.
- All RAG justfile recipes and connected doctor, semantic, resident-test, and terminology
  surfaces are absent with no replacement alias.
- Workflows, hooks, contributor documentation, and release guidance reference only the
  replacement surface.
- The two retired justfile ADRs remain superseded by the accepted justfile-design ADR;
  the Vaultspec graph and lifecycle-document checks report no new feature-local errors.
- Every Step is closed with a corresponding execution record before the plan is marked
  complete.
