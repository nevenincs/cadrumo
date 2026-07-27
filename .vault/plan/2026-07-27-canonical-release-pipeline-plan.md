---
tags:
  - '#plan'
  - '#canonical-release-pipeline'
date: '2026-07-27'
modified: '2026-07-27'
tier: L2
related:
  - '[[2026-07-27-canonical-release-pipeline-adr]]'
  - '[[2026-07-27-publication-lane-consolidation-adr]]'
  - '[[2026-07-27-pipeline-config-topology-adr]]'
  - '[[2026-07-27-canonical-release-pipeline-research]]'
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

# `canonical-release-pipeline` plan

### Phase `P01` - Version-identity guard

Close the live version-reuse hazard first: the burned-version ledger, then one all-destination identity authority wired into cohort seal and Gate 2, so 0.2.0 and 0.2.1 become refusable and a collision can never be minted or promoted again.

- [x] `P01.S01` - Create the burned-version ledger as a committed data file seeded with 0.2.0 and 0.2.1, each entry carrying version, burn date, and one-line reason, loaded by a typed reader, gate: uv run --no-sync pytest dev/release/tests/test_burned_versions.py -q passes with tests covering both seeded entries and refusal of a malformed or duplicate entry; `dev/release/burned_versions.toml, dev/release/version_identity.py, dev/release/tests/test_burned_versions.py`.
- [x] `P01.S02` - Extend the destination guard into one all-destination version-identity authority checking the three PyPI projects, the v-tag and release namespace including drafts, the monotonic manifest floor, and the burned ledger, refusing with the owning destination named, gate: uv run --no-sync pytest dev/release/tests -q -k version_identity passes with one refusal case exercised per destination class plus the burned-version and floor refusals; `dev/release/promote_python_cohort.py, dev/release/version_identity.py, dev/release/tests/test_promote_python_cohort.py`.
- [x] `P01.S03` - Invoke the identity authority at cohort seal time in the packaging workflow so sealing a version that is owned, burned, or not above the manifest floor refuses before any artifact uploads, gate: uv run --no-sync pytest dev/packaging/tests -q -k workflow passes with a conformance test pinning the seal job's guard invocation, full seal-refusal execution needs a CI dispatch and is flagged non-local; `.github/workflows/packaging-smoke.yml, dev/packaging/tests/`.
- [x] `P01.S04` - Replace the check-pypi-only destination guard in Gate 2 with the all-destination authority, gate: uv run --no-sync pytest dev/release/tests -q -k publish_release passes with the conformance test asserting no check-pypi-only invocation remains and the Gate 2 step invokes the authority; `.github/workflows/publish-release.yml, dev/release/tests/test_publish_release_workflow.py`.

### Phase `P07` - Generator-test coverage reinstatement

Reinstate the fourteen orphaned Homebrew and Scoop generator tests into a declared gate and add the guard that stops any test directory falling outside every lane again. Positioned second because these tests bind the formula and manifest to a real cohort, so they prove the channel-binding work the later phases land: two independent breakages accumulated invisibly while no lane ran them, and the author of the breaking change had no signal at all.

- [x] `P07.S17` - Wire the Homebrew and Scoop generator tests into the full-CI lane as a dedicated explicit-path serial invocation of packaging/homebrew/tests and packaging/scoop/tests, honoring their serial marker with a single-worker run rather than excluding it, sized into ci-full deliberately because their real sdist and wheel builds cost minutes that the per-push budget cannot absorb, gate: uv run --no-sync pytest packaging/homebrew/tests packaging/scoop/tests -q -n0 -m serial passes locally at 14 of 14 and a lane conformance test pins the ci-full invocation covering both paths; `.github/workflows/ci-full.yml, dev/ci/tests/`.
- [x] `P07.S18` - Add the lane-reachability gate asserting every test_*.py under the repository is selected by at least one declared pytest lane, computing reachability from pyproject testpaths, justfile recipes, and every workflow pytest invocation with both the path scope AND the marker expression modeled, since this incident's tests were excluded twice over, gate: uv run --no-sync pytest dev/ci/tests -q -k reachability passes and its injectable-root self-test plants an orphaned test file and asserts the gate reds; `dev/ci/tests/test_lane_reachability.py`.

### Phase `P02` - Promotion ordering inversion

Invert the promote job around irreversibility per P5: every reversible destination write lands before the sole irreversible PyPI upload, and every step converges idempotently on re-dispatch.

- [x] `P02.S05` - Invert the promote job's destination order to release creation with assets and docs payload, then Scoop, Homebrew, and marketplace pushes, then the PyPI upload last, gate: uv run --no-sync pytest dev/release/tests -q -k publish_release passes with the conformance test pinning PyPI as the final destination write; `.github/workflows/publish-release.yml, dev/release/tests/test_publish_release_workflow.py`.
- [x] `P02.S06` - Prove every destination step idempotent against its own prior success so a re-dispatch of the same cohort converges, using clobber or skip-existing semantics per destination, gate: uv run --no-sync pytest dev/release/tests dev/packaging/tests -q -k idempot passes over the helper functions, end-to-end re-dispatch convergence needs CI and is flagged non-local; `.github/workflows/publish-release.yml, dev/packaging/marketplace_publish.py, dev/release/tests/`.

### Phase `P03` - Second-lane deletion, repo side

Execute the repo-side half of issue 618: the retiring upload workflow and its conformance test are deleted with every reference swept, leaving Gate 3 the sole publication authority in the tree. The registry-side registration and environment deletions are the operator's OP-6 half.

- [x] `P03.S07` - Delete the retiring upload workflow and its conformance test and sweep every reference, gate: rg -i pypi-upload across the tree returns only vault records and history, and uv run --no-sync pytest dev/release/tests -q passes clean after the deletion; `.github/workflows/pypi-upload.yml, dev/release/tests/test_pypi_upload_workflow.py`.

### Phase `P04` - Marketplace supersession mechanism

Build the declared-supersession mechanism ruled by R6, which does not exist yet and must land before first publication: the cohort declares retired names, the merge tool removes them under the unchanged ownership rule, and the publish preflight refuses while a retired identity remains live.

- [x] `P04.S08` - Declare the superseded-names axis in the generated cohort marketplace manifest, seeded with the retired aeat plugin identity, gate: uv run --no-sync pytest dev/packaging/tests -q -k marketplace passes with the generator test asserting the declaration is emitted in every generated manifest; `dev/packaging/release_cohort.py, dev/packaging/cohort_manifest.py, dev/packaging/tests/`.
- [x] `P04.S09` - Teach the marketplace merge tool to remove a superseded entry and its subtree only where published_by matches this product or is absent, refusing a sibling-owned name identically to a takeover, gate: uv run --no-sync pytest dev/packaging/tests -q -k marketplace passes covering own-entry removal, publisher-less removal, sibling refusal, and idempotent re-run on an already-clean index; `dev/packaging/marketplace_publish.py, dev/packaging/tests/`.
- [x] `P04.S10` - Add the fail-closed publish preflight refusing while a retired name or retired-identity account metadata remains live and un-superseded in the marketplace index, with the refusal naming the supersession instruction, gate: uv run --no-sync pytest dev/packaging/tests -q -k preflight passes covering the refusal and the clean-pass cases; `dev/packaging/marketplace_publish.py, .github/workflows/publish-release.yml, dev/packaging/tests/`.

### Phase `P05` - Boundary detector extension

Extend the standing doc-privacy gate with the cross-project identifier class and the tracked-plus-staged-plus-untracked scan scope, closing the two measured blind spots that let this feature's own records carry a zone identifier while the gate was green.

- [x] `P05.S11` - Extend the doc-privacy gate with the cross-project identifier class, shape rules for 32-hex infrastructure ids, cloud role-identifier shapes, and owner-slash-repo slugs outside the declared reference set, plus fragment tokens for known private names, preserving the legal-attribution exemption untouched, gate: uv run --no-sync pytest dev/quality/tests/test_doc_privacy.py -q passes including a planted-violation self-test per new shape class that reds when its refusal is removed; `dev/quality/tests/test_doc_privacy.py`.
- [x] `P05.S12` - Widen the privacy scan scope from the tracked tree to tracked plus staged plus untracked-not-ignored files, gate: the same pytest invocation passes with a self-test that plants a violating untracked file in an injectable temporary repository root and asserts the gate reds, proving the extension is not tautological against the real repo state; `dev/quality/tests/test_doc_privacy.py`.

### Phase `P06` - Docs consequence delivery and runbook

Land the automated docs consequence workflow and retire the CI-refusal guard in the same change, both gated on the operator's OP-3 provisioning, then codify the bump-first runbook and the distribution-complete tripwire. Ordered last because it improves the pipeline rather than guarding it.

- [x] `P06.S13` - Author the docs consequence workflow triggered on release published and by dispatch, running on the self-hosted fleet, reading the deploy role from an environment-scoped variable with zero stored credentials, alerting on failure and never blocking the release, gate: a workflow conformance test pins the trigger set, runner labels, OIDC permissions, and the absence of secret literals and passes locally, live execution is BLOCKED on OP-3 and flagged non-local; `.github/workflows/docs-publish.yml, dev/deploy/tests/`.
- [ ] `P06.S14` - Remove the CI-refusal guard from the docs publisher in the same change that binds the consequence workflow to the protected docs environment, gate: uv run --no-sync pytest dev/deploy/tests -q passes with the guard's absence asserted and the build path exercised under CI markers, deployment against the live stack is BLOCKED on OP-3 and flagged non-local; `dev/deploy/docs_static_site.py, dev/deploy/frontend_static_site.py, dev/deploy/tests/`.
- [x] `P06.S15` - Codify the release runbook with the bump-first release-please step, the docs consequence, the distribution-complete tripwire, and the 0.1.0 first-version expectation, sweeping user docs where they describe the release flow, gate: uv run --no-sync pytest dev/docs/tests -m docs -q and the documented-command conformance test pass; `docs/, dev/docs/tests/`.
- [ ] `P06.S16` - Run the fresh-context honesty review against the campaign closure summary and persist it as a vault audit with every surfaced item tracked as a new Step or formally deferred with a named follow-up, gate: the audit document exists under .vault/audit and uv run --no-sync vaultspec-core vault plan status reports no checked Step without an exec record; `.vault/audit/`.

## Description

One plan executes the accepted three-record cluster. Phases P01, P02, and P03
implement the publication-lane record (P3 identity guard and burned-version
ledger, P5 ordering inversion, P4 lane deletion). Phase P04 implements the
delivery record's R6 declared-supersession mechanism, and Phase P06 its
R2/R3/R4 docs-consequence rulings plus the P2 bump-first runbook. Phase P05
implements the configuration-topology record's detector extension. Phase P07
is gate-integrity work surfaced during execution of the ADR cluster: the
fourteen Homebrew and Scoop generator tests that bind formula and manifest to
a real cohort were reachable by no lane at all - path-excluded by every
scoped invocation and marker-excluded by the default expression - which let
two independent breakages accumulate with no signal to their authors.
Ordering is by hazard, not by record: until P01.S01 lands, nothing in the
repository refuses re-minting 0.2.0 or 0.2.1 - two version strings the
public could download for weeks - so the ledger precedes everything, and P07
comes second because it is the gate that proves the channel-binding work
every later phase lands. Ground facts at authoring time: every version declaration reads
0.0.0, the first computed version will be 0.1.0, both partial releases and
their remote tags are deleted, and all four self-hosted runners are online.

Nothing in this plan publishes, pushes, arms a variable, or creates a
credential. Steps blocked on an operator decision name the OP and carry a
gate verifiable without it. Two operator halves run beside this plan and are
not Steps in it: the OP-6 registry-side deletions (Trusted Publishing
registrations and their environments) and the OP-3 provisioning that unblocks
P06.S13 and P06.S14.

## Steps

## Parallelization

P01 is strictly first and internally ordered S01 then S02, with S03 and S04
parallel after S02. P07 is second in display order but shares no files with
P01, so its two Steps (S17 then S18, since the reachability gate should
observe the newly wired lane) may run in parallel with P01. P03, P04 (S08,
S09), and P05 are independent of P01 and of each other and may run in
parallel with it. Hard serialization exists on
one file: `.github/workflows/publish-release.yml` is touched by P01.S04,
P02.S05, P02.S06, and P04.S10, so those four Steps land sequentially in that
order regardless of phase parallelism. P02 follows P01.S04 for that reason.
P06.S15 waits for P01 through P04 so the runbook describes the landed shape,
P06.S13 and S14 are schedulable any time after OP-3 but must land together in
one change, and P06.S16 is last by definition.

## Verification

Mission success is measured, not asserted. The plan is complete when every
Step is closed with its named gate green and the following hold together:

- The fourteen generator tests pass 14 of 14 under the explicit serial
  invocation, a lane conformance test pins their ci-full home, and the
  lane-reachability gate is green on the tree while redding on a planted
  orphaned test file.
- The identity guard refuses a seeded burned version and a below-floor
  version in unit tests, and both workflow conformance suites pin its
  invocation at seal and at Gate 2 with no check-pypi-only path remaining.
- The publish workflow conformance suite pins PyPI as the final destination
  write.
- `rg -i pypi-upload` over the tree matches only vault records and history.
- The marketplace suite proves supersession removes exactly the own or
  publisher-less retired entry, refuses a sibling-owned name, and the
  preflight refuses a live retired identity.
- The extended privacy gate reds on a planted cross-project identifier and on
  a planted violating untracked file, and stays green on the clean tree.
- The docs gates pass with the runbook updated, and the consequence workflow
  conformance test passes even while OP-3 keeps live execution blocked.
- A fresh-context honesty review audit exists and every checked Step carries
  an exec record, per plan-closure discipline.

Full-tree gates run under the shared-worktree discipline: a red owned by a
peer campaign is recorded and attributed, never absorbed silently into this
plan's completion claim.
