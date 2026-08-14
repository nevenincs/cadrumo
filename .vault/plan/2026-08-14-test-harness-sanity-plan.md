---
tags:
  - '#plan'
  - '#test-harness-sanity'
date: '2026-08-14'
modified: '2026-08-14'
body_hash: 'sha256:6c65fd6b325e281529863ae694ab87ef3a10b1e4e44097eb2eeb375d4659b569'
tier: L3
related:
  - '[[2026-08-14-test-harness-sanity-successor-adr]]'
  - '[[2026-04-17-pytest-only-testing-adr]]'
  - '[[2026-06-05-test-topology-refactor-adr]]'
  - '[[2026-07-25-test-harness-honesty-adr]]'
  - '[[2026-08-05-ci-lane-deconflation-adr]]'
  - '[[2026-08-14-test-harness-sanity-two-lane-campaign-research]]'
---

<!-- RETIRED: W01, W02, W03, W04, W05, P02, P03, P04, P05, P06, P07, P08, P09, P10, P11, P12, P13, P14, P15, S01, S02, S03, S04, S05, S06, S07, S08, S09, S10, S11, S12, S13, S14, S15, S16, S17, S18, S19, S20, S21, S22, S23, S24, S25, S26, S27, S28, S29, S30, S31, S32, S33, S34, S35, S36, S37, S38, S39, S40, S41, S42, S43, S44, S45, S46 -->

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
- [ ] `W07.P18.S54` - Canonicalize the secure-runtime-profile cluster after coordinating active secure-sql ownership; `src/cadrumo/tests/secure_sql.py, src/cadrumo/tests/profile_capsule.py`.
- [x] `W07.P18.S55` - Canonicalize the exact secure-object-repository cluster without merging its divergent shape; `src/cadrumo/application/aggregation/tests, src/cadrumo/application/modelo/tests`.
- [x] `W07.P18.S56` - Canonicalize fixed-master-key fixtures across persistence storage tests; `src/cadrumo/adapters/persistence/storage`.

### Phase `W07.P19` - canonicalize profile CLI and schema fixtures

Consolidate repeated profile and schema setup only within constraint-compatible ownership boundaries.

- [ ] `W07.P19.S57` - Canonicalize isolated profile-storage fixtures used by wizard and CLI profile tests; `src/cadrumo/application/wizard/tests, src/cadrumo/entrypoints/cli/tests`.
- [ ] `W07.P19.S58` - Canonicalize the overview CLI backend fixture shape at its narrowest owner; `src/cadrumo/entrypoints/cli/tests/test_overview_verbs.py, src/cadrumo/entrypoints/cli/conftest.py`.
- [ ] `W07.P19.S59` - Canonicalize the open-bucket CLI backend shape without merging storage lifecycles; `src/cadrumo/entrypoints/cli/tests/test_ledger_view_ux.py, src/cadrumo/entrypoints/cli/conftest.py`.
- [x] `W07.P19.S60` - Canonicalize schema-loader fixtures while preserving proven scope; `src/cadrumo/domain/user_profile/tests`.

### Phase `W07.P20` - canonicalize modelo and registry fixtures

Use existing modelo and registry owners to remove local redeclarations and repeated immutable snapshots.

- [x] `W07.P20.S61` - Remove local redeclarations of the canonical modelo repositories fixture; `src/cadrumo/application/modelo/tests`.
- [x] `W07.P20.S62` - Canonicalize the M130 committed registry snapshot family; `src/cadrumo/domain/calculations/registry/tests`.
- [ ] `W07.P20.S63` - Canonicalize the M180 committed registry snapshot family; `src/cadrumo/domain/calculations/registry/tests`.
- [ ] `W07.P20.S64` - Canonicalize the M100 2024 committed registry snapshot family; `src/cadrumo/domain/calculations/registry/tests`.
- [ ] `W07.P20.S65` - Canonicalize the M200 development registry snapshot family; `dev/registry/tests`.

### Phase `W07.P21` - adjudicate every remaining fixture and support factory

Complete root source development and packaging census remediation with no unclassified fixture.

- [ ] `W07.P21.S66` - Adjudicate and canonicalize every remaining source-tree fixture cluster in the census; `src/cadrumo`.
- [ ] `W07.P21.S67` - Adjudicate and canonicalize every remaining development fixture cluster in the census; `dev`.
- [ ] `W07.P21.S68` - Adjudicate and canonicalize every remaining packaging fixture cluster in the census; `packaging`.
- [ ] `W07.P21.S69` - Adjudicate root conftest and explicit-import support factories and remove substitute owners; `conftest.py, src/cadrumo/tests`.
- [ ] `W07.P21.S70` - Make census drift fail on any unclassified or substitutable duplicate fixture; `dev/quality/tests/test_fixture_census.py`.

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
- [ ] `W07.P24.S83` - Measure routine unit and dedicated harness runtime without nested outer xdist; `dev/ci/tests/test_machine_aware_load.py`.

### Phase `W07.P25` - deconflate central test responsibility

Move owner-specific tests to domain homes and correct package-root fixture rationale.

- [ ] `W07.P25.S84` - Move and rename the core i18n default-language test to its owner; `src/cadrumo/tests/test_cli.py, src/cadrumo/core/i18n/tests`.
- [ ] `W07.P25.S85` - Move profile output-language integration tests to their application owner; `src/cadrumo/tests/test_output_language.py, src/cadrumo/application/user_profile/tests`.
- [ ] `W07.P25.S86` - Replace stale naked-test rationale with current distributed visibility requirements; `src/cadrumo/conftest.py`.
- [ ] `W07.P25.S87` - Add a central-harness ownership gate without a file allowlist; `src/cadrumo/tests/test_test_inventory.py`.

## Wave `W08` - verify ownership performance and honesty

Independently review both lanes and prove the full mandate with focused lane collection structural and VaultSpec gates.

### Phase `W08.P26` - verify fixture and harness invariants

Run exact focused and lane-level gates for each migrated surface and enforcement boundary.

- [ ] `W08.P26.S88` - Run the fixture census and require zero unclassified or substitutable duplicates; `dev/quality/fixture_ownership.toml`.
- [ ] `W08.P26.S89` - Run marker banned-import topology ownership and no-monkeypatch gates; `src/cadrumo/tests`.
- [ ] `W08.P26.S90` - Run the dedicated harness lane and verify non-vacuity and independent verdict; `justfile, .github/workflows/ci.yml`.
- [ ] `W08.P26.S91` - Run unit and integration recipes and compare measured runtime to baseline; `justfile`.

### Phase `W08.P27` - perform independent architecture and code review

Use fresh-context Sol review to validate ownership real behavior performance and absence of bridges.

- [ ] `W08.P27.S92` - Audit every fixture disposition against current consumers and lifecycle; `.vault/audit`.
- [ ] `W08.P27.S93` - Audit every original high-through-low finding against current code and evidence; `.vault/audit`.
- [ ] `W08.P27.S94` - Run the close honesty review and action every surviving item; `.vault/audit`.

### Phase `W08.P28` - close broad verification and provenance

Bind collection VaultSpec execution records and plan state into one auditable completion boundary.

- [ ] `W08.P28.S95` - Run full first-party collection and retain complete status and errors; `pyproject.toml`.
- [ ] `W08.P28.S96` - Run feature-scoped and repository-wide VaultSpec checks without rewriting unrelated debt; `.vault`.
- [ ] `W08.P28.S97` - Create and validate one execution record per completed Step; `.vault/exec/2026-08-14-test-harness-sanity`.
- [ ] `W08.P28.S98` - Prove every mandate requirement has authoritative evidence and no work remains; `.vault/plan/2026-08-14-test-harness-sanity-plan.md`.

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
