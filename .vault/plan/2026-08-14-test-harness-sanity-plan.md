---
tags:
  - '#plan'
  - '#test-harness-sanity'
date: '2026-08-14'
tier: L3
related:
  - '[[2026-08-14-test-harness-sanity-successor-adr]]'
  - '[[2026-06-05-test-topology-refactor-adr]]'
  - '[[2026-07-25-test-harness-honesty-adr]]'
  - '[[2026-08-05-ci-lane-deconflation-adr]]'
  - '[[2026-08-14-test-harness-sanity-two-lane-campaign-research]]'
modified: '2026-08-25'
body_hash: 'sha256:3f4a6f16361ab631b31dc674e762c8845f5cb5ef3721d080b020f10435c9cfd5'
---

<!-- RETIRED: W01, W02, W03, W04, W05, P02, P03, P04, P05, P06, P07, P08, P09, P10, P11, P12, P13, P14, P15, S01, S02, S03, S04, S05, S06, S07, S08, S09, S10, S11, S12, S13, S14, S15, S16, S17, S18, S19, S20, S21, S22, S23, S24, S25, S26, S27, S28, S29, S30, S31, S32, S33, S34, S35, S36, S37, S38, S39, S40, S41, S42, S43, S44, S45, S46, S111, S121, S122, S138 -->

# `test-harness-sanity` plan

Canonicalize every test fixture and repair the complete harness audit through
two parallel, independently reviewed implementation lanes.

## Description

This L3 roll-up plan executes the accepted test-harness successor decision and
the existing pytest-only, topology, test-honesty, and CI verdict-boundary
decisions. Wave W06 creates the executable fixture census and dedicated harness
verdict used by both lanes. Wave W07 runs fixture canonicalization in Phases
P18-P21 concurrently with audit remediation in Phases P22-P25. Wave W08 is an
independent verification and honesty boundary; it does not close from focused
green tests alone.

The fixture lane covers root configuration, `src`, `dev`, and `packaging`.
Every disposition must preserve name, scope, autouse behavior, constraints,
teardown, and consumer visibility or document why a deliberate narrowing is
correct. Exact body equality is candidate evidence, never automatic authority.
The harness lane repairs all high-through-low findings without suppressions,
allowlists, compatibility aliases, bridge fixtures, mocks, monkeypatches,
skips, or xfails.

## Steps

## Wave `W06` - establish executable ownership and lane foundations

Create the authoritative fixture census and harness-lane contract that the two parallel implementation lanes consume.

### Phase `W06.P16` - build the complete fixture census authority

Produce a reproducible census that classifies every fixture before any duplicate is removed.

- [x] `W06.P16.S47` - Implement the AST-backed fixture census with decorator scope autouse constraint owner and consumer fields; `dev/quality/fixture_census.py`.
- [x] `W06.P16.S48` - Add real-tree census tests that prove root source development and packaging coverage and reject collapse; `dev/quality/tests/test_fixture_census.py`.
- [x] `W06.P16.S49` - Generate the complete fixture ownership manifest with no unclassified records; `dev/quality/fixture_ownership.toml`.

### Phase `W06.P17` - establish the independently verdictable harness lane

Give installed-hook and full-corpus proofs one explicit outer-serial verdict before moving expensive tests.

- [x] `W06.P17.S50` - Define the outer-serial harness recipe with explicit membership non-vacuity and exit-status preservation; `justfile`.
- [x] `W06.P17.S51` - Enroll the harness verdict in CI independently from unit and integration verdicts; `.github/workflows/ci.yml`.
- [x] `W06.P17.S52` - Prove the harness recipe selects every declared member and fails when membership collapses; `dev/ci/tests/test_ci_workflow.py`.

## Wave `W07` - execute two remediation lanes in parallel

Run codebase-wide fixture canonicalization and the complete audit-remediation lane concurrently under disjoint Phase ownership after W06 lands.

### Phase `W07.P18` - canonicalize secure-runtime and repository fixtures

Remove substitutable secure runtime and repository fixtures while preserving lifecycle and visibility.

- [x] `W07.P18.S53` - Canonicalize duplicated LLM secure-runtime fixtures at their narrowest common owner; `src/cadrumo/llm/conftest.py, src/cadrumo/adapters/outbound/llm/conftest.py`.
- [x] `W07.P18.S54` - Canonicalize the secure-runtime-profile cluster after coordinating active secure-sql ownership; `src/cadrumo/tests/secure_sql.py, src/cadrumo/tests/profile_capsule.py`.
- [x] `W07.P18.S55` - Canonicalize the exact secure-object-repository cluster without merging its divergent shape; `src/cadrumo/application/aggregation/tests, src/cadrumo/application/modelo/tests`.
- [x] `W07.P18.S56` - Canonicalize fixed-master-key fixtures across persistence storage tests; `src/cadrumo/adapters/persistence/storage`.

### Phase `W07.P19` - canonicalize profile CLI and schema fixtures

Consolidate repeated profile and schema setup only within constraint-compatible ownership boundaries.

- [x] `W07.P19.S57` - Canonicalize isolated profile-storage fixtures used by wizard and CLI profile tests; `src/cadrumo/application/wizard/tests, src/cadrumo/entrypoints/cli/tests`.
- [x] `W07.P19.S58` - Canonicalize the overview CLI backend fixture shape at its narrowest owner; `src/cadrumo/entrypoints/cli/tests/test_overview_verbs.py, src/cadrumo/entrypoints/cli/conftest.py`.
- [x] `W07.P19.S59` - Canonicalize the open-bucket CLI backend shape without merging storage lifecycles; `src/cadrumo/entrypoints/cli/tests/test_ledger_view_ux.py, src/cadrumo/entrypoints/cli/conftest.py`.
- [x] `W07.P19.S60` - Canonicalize schema-loader fixtures while preserving proven scope; `src/cadrumo/domain/user_profile/tests`.

### Phase `W07.P20` - canonicalize modelo and registry fixtures

Use existing modelo and registry owners to remove local redeclarations and repeated immutable snapshots.

- [x] `W07.P20.S61` - Remove local redeclarations of the canonical modelo repositories fixture; `src/cadrumo/application/modelo/tests`.
- [x] `W07.P20.S62` - Canonicalize the M130 committed registry snapshot family; `src/cadrumo/domain/calculations/registry/tests`.
- [x] `W07.P20.S63` - Canonicalize the M180 committed registry snapshot family; `src/cadrumo/domain/calculations/registry/tests`.
- [x] `W07.P20.S64` - Canonicalize the M100 2024 committed registry snapshot family; `src/cadrumo/domain/calculations/registry/tests`.
- [x] `W07.P20.S65` - Canonicalize the M200 development registry snapshot family; `dev/registry/tests`.

### Phase `W07.P21` - adjudicate every remaining fixture and support factory

Complete root source development and packaging census remediation with no unclassified fixture.

- [x] `W07.P21.S66` - Adjudicate and canonicalize every remaining source-tree fixture cluster in the census; `src/cadrumo`.
- [x] `W07.P21.S67` - Adjudicate and canonicalize every remaining development fixture cluster in the census; `dev`.
- [x] `W07.P21.S68` - Adjudicate and canonicalize every remaining packaging fixture cluster in the census; `packaging`.
- [x] `W07.P21.S69` - Adjudicate root conftest and explicit-import support factories and remove substitute owners; `conftest.py, src/cadrumo/tests`.
- [x] `W07.P21.S70` - Make census drift fail on any unclassified or substitutable duplicate fixture; `dev/quality/tests/test_fixture_census.py`.
- [x] `W07.P21.S102` - Delete the production re-export bridge the import-hygiene gate reports and repoint its consumers; `src/cadrumo/adapters/persistence/storage/custody`.
- [x] `W07.P21.S103` - Give the re-export-bridge gate a declared reach over the test tree instead of silent exclusion; `dev/quality/import_hygiene_scan.py`.
- [x] `W07.P21.S104` - Collapse every identical-constraint fixture cluster to one definition preserving scope and autouse reach; `src/cadrumo`.
- [x] `W07.P21.S105` - Key the ownership manifest disposition on full constraint shape rather than repeated name; `dev/quality/fixture_ownership.py, dev/quality/tests/test_fixture_census.py`.
- [x] `W07.P21.S106` - Detect one fixture behaviour living under many names by keying the census on body rather than name; `dev/quality/fixture_census.py, dev/quality/tests/test_fixture_census.py`.
- [x] `W07.P21.S107` - Give each aliased fixture behaviour one canonical home and one name preserving per-site lifecycle; `src/cadrumo`.
- [x] `W07.P21.S108` - Adjudicate the substitutable secure-storage-root fixture pair the manifest now refuses on; `src/cadrumo/application/setup/tests, src/cadrumo/application/wizard/tests`.
- [x] `W07.P21.S109` - Classify factory-bound fixtures as manifest rows with per-binding identity and argument evidence; `dev/quality/fixture_ownership.py, dev/quality/tests/test_fixture_census.py`.
- [x] `W07.P21.S110` - Sweep test helper functions assertion helpers and builders for drift the fixture census cannot see; `src/cadrumo, dev`.

### Phase `W07.P22` - unify marker and live-import enforcement

Apply collection policy exactly once from the root and prove domain-local live reach.

- [x] `W07.P22.S71` - Promote banned-live-import enforcement into the shared root policy helper; `src/cadrumo/tests/_marker_hook.py`.
- [x] `W07.P22.S72` - Make the repository root the sole collection-policy hook owner; `conftest.py`.
- [x] `W07.P22.S73` - Remove duplicate marker traversal and live-policy ownership from the child conftest; `src/cadrumo/tests/conftest.py`.
- [x] `W07.P22.S74` - Add real subprocess proofs for domain-local banned live imports and clean controls; `src/cadrumo/tests/test_marker_integrity.py`.

### Phase `W07.P23` - remove forbidden monkeypatch controls

Replace every reported production mutation with real input or explicit production seams.

- [x] `W07.P23.S75` - Replace the OFX optional-extra monkeypatch with real behavior; `src/cadrumo/adapters/inbound/financial/providers/tests/test_ofx.py`.
- [x] `W07.P23.S76` - Replace previous-filing exception mutation with reachable real behavior; `src/cadrumo/application/calculations/tests/test_previous_filing_absence_versus_malformed.py`.
- [x] `W07.P23.S77` - Replace relation-allowance mutation with an explicit production input; `src/cadrumo/domain/calculations/registry/tests/test_relation_closure.py`.
- [x] `W07.P23.S78` - Replace previous-filing revision-selector mutation with real registry input; `src/cadrumo/domain/calculations/registry/tests/test_validate_previous_filing_year_coverage.py`.
- [x] `W07.P23.S79` - Restore the no-monkeypatch gate and discriminating controls to green; `src/cadrumo/tests/test_monkeypatch_inventory.py`.

### Phase `W07.P24` - separate expensive harness proofs from unit

Retain installed-process evidence without nested pools or recursive collection in routine unit execution.

- [x] `W07.P24.S80` - Move installed-hook worker-pool proofs out of routine unit execution; `src/cadrumo/tests/test_worker_count_hook.py`.
- [x] `W07.P24.S81` - Move full-corpus collectability out of unit while retaining bounded controls; `src/cadrumo/tests/test_every_test_module_is_collectable.py`.
- [x] `W07.P24.S82` - Align worker tests with repository-owned six-worker authority and explicit overrides; `src/cadrumo/tests/_worker_count_hook.py, src/cadrumo/tests/test_worker_count_hook.py`.
- [x] `W07.P24.S83` - Measure routine unit and dedicated harness runtime without nested outer xdist; `dev/ci/tests/test_machine_aware_load.py`.
- [x] `W07.P24.S99` - Resolve justfile variables and model lane exclusions in the one lane authority; `dev/ci/lane_reachability.py, src/cadrumo/tests/test_lane_reachability.py`.
- [x] `W07.P24.S100` - Delete the private justfile parsers in the CI gate modules and consume the lane authority; `dev/ci/tests/test_machine_aware_load.py, dev/ci/tests/test_ci_workflow.py`.
- [x] `W07.P24.S101` - Derive the first-party corpus boundary from the tracked-file authority instead of a directory name list; `src/cadrumo/tests/test_every_test_module_is_collectable.py`.

### Phase `W07.P25` - deconflate central test responsibility

Move owner-specific tests to domain homes and correct package-root fixture rationale.

- [x] `W07.P25.S84` - Move and rename the core i18n default-language test to its owner; `src/cadrumo/tests/test_cli.py, src/cadrumo/core/i18n/tests`.
- [x] `W07.P25.S85` - Move profile output-language integration tests to their application owner; `src/cadrumo/tests/test_output_language.py, src/cadrumo/application/user_profile/tests`.
- [x] `W07.P25.S86` - Replace stale naked-test rationale with current distributed visibility requirements; `src/cadrumo/conftest.py`.
- [x] `W07.P25.S87` - Add a central-harness ownership gate without a file allowlist; `src/cadrumo/tests/test_test_inventory.py`.

## Wave `W08` - verify ownership performance and honesty

Independently review both lanes and prove the full mandate with focused lane collection structural and VaultSpec gates.

### Phase `W08.P26` - verify fixture and harness invariants

Run exact focused and lane-level gates for each migrated surface and enforcement boundary.

- [x] `W08.P26.S88` - Run the fixture census and require zero unclassified or substitutable duplicates; `dev/quality/fixture_ownership.toml`.
- [x] `W08.P26.S89` - Run marker banned-import topology ownership and no-monkeypatch gates; `src/cadrumo/tests`.
- [x] `W08.P26.S90` - Run the dedicated harness lane and verify non-vacuity and independent verdict; `justfile, .github/workflows/ci.yml`.
- [x] `W08.P26.S91` - Run unit and integration recipes and compare measured runtime to baseline; `justfile`.

### Phase `W08.P27` - perform independent architecture and code review

Use fresh-context Sol review to validate ownership real behavior performance and absence of bridges.

- [x] `W08.P27.S92` - Audit every fixture disposition against current consumers and lifecycle; `.vault/audit`.
- [x] `W08.P27.S93` - Audit every original high-through-low finding against current code and evidence; `.vault/audit`.
- [x] `W08.P27.S94` - Run the close honesty review and action every surviving item; `.vault/audit`.

### Phase `W08.P28` - close broad verification and provenance

Bind collection VaultSpec execution records and plan state into one auditable completion boundary.

- [x] `W08.P28.S95` - Run full first-party collection and retain complete status and errors; `pyproject.toml`.
- [x] `W08.P28.S96` - Run feature-scoped and repository-wide VaultSpec checks without rewriting unrelated debt; `.vault`.
- [x] `W08.P28.S97` - Create and validate one execution record per completed Step; `.vault/exec/2026-08-14-test-harness-sanity`.
- [x] `W08.P28.S98` - Prove every mandate requirement has authoritative evidence and no work remains; `.vault/plan/2026-08-14-test-harness-sanity-plan.md`.

## Wave `W09` - reopen the census on the body-keyed axis

A second team re-scanned the test corpus after W08 closed and found duplication the name-keyed census could not reach: exact-duplicate helper bodies, near-identical drifted variants, and semantically mirrored reimplementations under different names in different libraries. The originating audit already named this axis problem -- thirteen behaviours under thirty-eight names -- and recorded the census as unable to reach a verdict on this tree. This wave carries that second sweep, its consolidations, and the census records the constraint requires, so both teams see one plan.

### Phase `W09.P29` - consolidate exact-duplicate helper bodies found by the body-keyed rescan

Twenty-five file-disjoint batches of byte-identical helper bodies, partitioned by union-find over the task-to-file graph so no two workers touch one file. Each slice consolidates at the narrowest common owner, deletes every redundant definition outright with no bridge or alias, and compares failures as a set rather than a count because parts of this tree are deliberately red.

- [x] `W09.P29.S112` - Consolidate the thirteen observation-lookup helpers into one narrowest-owner helper carrying the return annotation every original lacked; `src/cadrumo/application/calculations/tests/_observation_lookup_support.py`.
- [x] `W09.P29.S113` - Consolidate the ten attribute-replacement context managers onto the documented submodule-direct convention and preserve the monkeypatch-ban rationale; `src/cadrumo/tests/attribute_scope.py`.
- [x] `W09.P29.S114` - Consolidate the twelve convenio rate resolvers and prove every per-country treaty rate and legal citation stayed in its own file; `src/cadrumo/application/calculations/tests/_convenio_rate_support.py`.
- [x] `W09.P29.S115` - Consolidate the secure-object repository builders into the existing support module and remove the unused imports a prior slice left behind (the original "five" was wrong, the tree carries two canonical builders plus a third justified-divergence construction); `src/cadrumo/adapters/persistence/storage/sql/tests/_secure_objects_support.py`.
- [x] `W09.P29.S116` - Consolidate the five docs HTTP server helpers to the strictest cleanup form and close the listening socket every copy leaked; `dev/docs/tests/_http_serve_support.py`.
- [x] `W09.P29.S117` - Collapse the sixty-six structurally identical modelo 131 modulos tests into parametrized cases without losing a single expected value or IAE citation; `src/cadrumo/domain/calculations/registry/tests/test_modelo_131_modulos_engine*.py`.
- [x] `W09.P29.S118` - Consolidate the ledger corpus match and oracle-rule helpers and upgrade the existing shared copies to the stricter guarded variant; `src/cadrumo/entrypoints/cli/tests/_ledger_corpus_support.py`.
- [ ] `W09.P29.S119` - Consolidate duplicate secure-object ephemeral repository test helpers behind the canonical shared support owner while preserving each caller's database-path and key-lifecycle contract; `src/cadrumo/adapters/persistence/storage/sql/tests/_secure_objects_support.py; src/cadrumo/adapters/persistence/storage/sql/tests/test_secure_object_write_batching.py; src/cadrumo/adapters/persistence/storage/sql/tests/test_secure_objects_part2.py; dev/quality/tests/test_helper_body_census.py`.
- [x] `W09.P29.S120` - Write one census record per consolidated cluster proving substitutability and naming the canonical owner, as the fixture-deletion constraint requires; `.vault/audit`.

### Phase `W09.P30` - adjudicate drifted variants and semantically mirrored reimplementations

The classes the name-keyed census cannot reach. Drift is scored by structural similarity over normalised AST node sequences; semantic mirrors are found only by meaning-based search, since they share neither name nor structure. Both are adjudicated before any edit: a copy that looks interchangeable and silently is not is more dangerous than an honest duplicate.

- [x] `W09.P30.S123` - Migrate the under-adopted canonical locale and loader-directory fixture homes onto their existing owners rather than creating new ones; `src/cadrumo/domain/calculations/registry/tests`.
- [x] `W09.P30.S124` - Sweep the corpus by meaning for reimplementations sharing neither name nor structure and record which could not have been reached by name or grep; `src/cadrumo, dev`.
- [x] `W09.P30.S125` - Re-key the duplication gate on body rather than name so a renamed twin cannot sit outside its own comparison; `dev/quality`.
- [x] `W09.P30.S126` - Sweep the thirty-seven pre-provisioned-bucket isolated-backend fixtures onto the canonical factory after extending it with settings and profile override passthroughs; `src/cadrumo/tests/active_profile_isolated_backend_fixture.py, src/cadrumo/entrypoints/cli/tests`.
- [x] `W09.P30.S127` - Converge the two independently written synthetic text-layer PDF builders and the four differently-named twins onto the canonical fixture; `src/cadrumo/tests/pdf_fixtures.py, src/cadrumo/application/live/tests/_notification_document_support.py`.
- [x] `W09.P30.S128` - Fold the four differently-named review-package builders onto a path-returning sibling of the canonical bytes builder; `src/cadrumo/application/modelo/tests, src/cadrumo/entrypoints/cli/tests`.
- [x] `W09.P30.S129` - Route the secure-object namespace registration mirror in the persistence package to an owner both test packages may import; `src/cadrumo/adapters/persistence/operations/tests`.
- [x] `W09.P30.S130` - Consolidate the drifted release-cohort builders onto a deterministic clock and retire the wall-clock variant; `dev/packaging/tests/_release_cohort_support.py`.
- [x] `W09.P30.S131` - Re-consolidate the worked-example oracle input reader after a concurrent edit deleted the shared function and pasted its body into three consumers, then rename it clear of the manual-input allowlist vocabulary; `src/cadrumo/domain/calculations/registry/tests/_manual_oracle_support.py`.
- [x] `W09.P30.S132` - Converge the hand-spelled CLI runtime isolation fixture onto the taxonomy-derived canonical helper, closing a storage-path defect the canonical docstring records as already fixed elsewhere; `src/cadrumo/entrypoints/cli/tests/test_workflow_surface.py`.
- [x] `W09.P30.S133` - Determine whether any production path rebuilds the transactions or invoices directory from the taxonomy rather than the resolved setting, which would make the drifted override a live defect rather than a self-consistent one; `src/cadrumo/core, src/cadrumo/application`.
- [x] `W09.P30.S134` - Sweep every test HTTP server for the shutdown-close-join triad and close the socket and thread leaks that accumulate under parallel execution; `dev/docs/tests, src/cadrumo/adapters/outbound`.
- [x] `W09.P30.S135` - Move the in-memory engine disposal in the hash-column-width test inside a finally so a failing assertion cannot skip it; `src/cadrumo/adapters/persistence/storage/sql/tests/test_hash_column_widths.py`.
- [x] `W09.P30.S136` - Close the live-write declaration helper still duplicated in the evaluation tree, or record the cross-tree import direction as the standing reason it cannot move; `dev/agent_eval/tests/test_confirmation_gate_golden.py`.
- [x] `W09.P30.S137` - Sweep key providers and encrypted sessions for guaranteed teardown, the one resource class left unexamined, adjudicating each of the 15 EphemeralMasterKeyProvider constructions that are assigned without ever being context-managed as helper-managed or leaking; `15 EphemeralMasterKeyProvider constructions are assigned without ever being context-managed and each needs adjudicating as helper-managed or leaking; `src/cadrumo/adapters/persistence/storage`.
- [x] `W09.P30.S139` - Migrate the CLI-surface workflow tests off application-layer profile seeding onto the credential-registering door so the custody envelope opens under the configured passphrase; `src/cadrumo/entrypoints/cli/tests/test_workflow_surface.py`.
- [x] `W09.P30.S140` - Record the fourth storage-plus-auth isolation composition in the isolated-backend cluster census so the cluster count reflects every known site; `src/cadrumo/entrypoints/cli/tests/_cli_surface_support.py`.
- [x] `W09.P30.S141` - Treat a body-duplicate that closes over a same-named module constant as its own triage bucket, since the safe fix is to parameterise the constant rather than delete the duplicate; `dev/quality/helper_body_census.py`.
- [x] `W09.P30.S142` - Delete the storage-root override that a nested call silently supersedes, so a reordered context tuple cannot start pointing at the wrong root; `src/cadrumo/entrypoints/cli/_config/tests/_isolated_storage_fixture.py`.
- [x] `W09.P30.S143` - Rename the local isolation fixture that shadows the canonical one imported into the same module; `src/cadrumo/entrypoints/cli/tests/test_cli_workflow_verification.py`.
- [x] `W09.P30.S144` - Converge the two remaining inline profile-isolation compositions onto the canonical factory, dropping a second occurrence of the superseded storage-root override for free; `src/cadrumo/entrypoints/cli/tests/_isolated_profile_storage_fixtures.py`.
- [x] `W09.P30.S145` - Determine whether any current door can still write an unnormalised regime value, since the retired wizard may have been the only path that exercised read-time normalisation; `src/cadrumo/application/wizard, src/cadrumo/domain/user_profile`.

## Parallelization

W06 is a hard prerequisite. Within W06, P16 and P17 may run concurrently after
their file ownership is assigned. In W07, fixture Phases P18-P21 and harness
Phases P22-P25 are the two mandated parallel lanes. Phases inside each lane may
also run concurrently where their listed paths do not overlap. P18.S54 waits
for active peer ownership of `secure_sql.py` and `profile_capsule.py` to settle
or coordinate explicitly; that sequencing does not narrow P18 or P21.

W08 starts only after every W07 Step has an implementation record and focused
gate. P27 is assigned to fresh-context Sol reviewers and must not be performed
by the Terra implementers whose work it audits.

## Verification

The campaign is complete only when all of the following are true:

- The live AST census covers every pytest fixture under root configuration,
  `src`, `dev`, and `packaging`, contains no unclassified record, and reports
  no substitutable duplicate owner.
- Every migrated cluster passes representative real-behavior tests from each
  former consumer subtree and a collection/visibility proof.
- Root collection applies marker and banned-live-import policy once to every
  relevant module, including domain-local live tests outside the central
  harness.
- The no-monkeypatch inventory and its discriminating controls pass with no
  allowlist, suppression, or renamed equivalent.
- Routine unit execution launches neither nested xdist width probes nor the
  full-corpus recursive collector; the dedicated outer-serial harness verdict
  runs both real proofs and fails on empty membership.
- Owner-specific tests no longer inhabit `src/cadrumo/tests`, and the central
  ownership gate rejects recurrence by property rather than file allowlist.
- Focused gates, the dedicated harness lane, normal unit and integration
  recipes, and full first-party collection have current captured outcomes with
  their exact verification boundaries.
- Fresh-context Sol review finds no unresolved high-through-low audit item,
  fixture ownership ambiguity, lifecycle regression, compatibility bridge, or
  completion-criterion narrowing.
- Every checked Step has a matching execution record, the plan validator is
  clean, feature-scoped VaultSpec checks pass, and repository-wide VaultSpec
  debt is reported separately without being rewritten to manufacture green.
