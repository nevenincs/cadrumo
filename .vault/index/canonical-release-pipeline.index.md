---
generated: true
tags:
  - '#index'
  - '#canonical-release-pipeline'
date: '2026-08-16'
modified: '2026-08-16'
body_schema: 'body-v1'
body_hash: 'sha256:cd4c7b9a81e5d787562fdf32e6a251437e004fe1f5eabe2b8d6ab0d8d2a4504d'
related:
  - '[[2026-07-27-canonical-release-pipeline-P01-S01]]'
  - '[[2026-07-27-canonical-release-pipeline-P01-S02]]'
  - '[[2026-07-27-canonical-release-pipeline-P01-S03]]'
  - '[[2026-07-27-canonical-release-pipeline-P01-S04]]'
  - '[[2026-07-27-canonical-release-pipeline-P02-S05]]'
  - '[[2026-07-27-canonical-release-pipeline-P02-S06]]'
  - '[[2026-07-27-canonical-release-pipeline-P03-S07]]'
  - '[[2026-07-27-canonical-release-pipeline-P04-S08]]'
  - '[[2026-07-27-canonical-release-pipeline-P04-S09]]'
  - '[[2026-07-27-canonical-release-pipeline-P04-S10]]'
  - '[[2026-07-27-canonical-release-pipeline-P05-S11]]'
  - '[[2026-07-27-canonical-release-pipeline-P05-S12]]'
  - '[[2026-07-27-canonical-release-pipeline-P06-S13]]'
  - '[[2026-07-27-canonical-release-pipeline-P06-S14]]'
  - '[[2026-07-27-canonical-release-pipeline-P06-S15]]'
  - '[[2026-07-27-canonical-release-pipeline-P06-S16]]'
  - '[[2026-07-27-canonical-release-pipeline-P07-S17]]'
  - '[[2026-07-27-canonical-release-pipeline-P07-S18]]'
  - '[[2026-07-27-canonical-release-pipeline-adr]]'
  - '[[2026-07-27-canonical-release-pipeline-campaign-close-honesty-review-audit]]'
  - '[[2026-07-27-canonical-release-pipeline-plan]]'
  - '[[2026-07-27-canonical-release-pipeline-research]]'
---

# `canonical-release-pipeline` feature index

Auto-generated index of all documents tagged with `#canonical-release-pipeline`.

## Documents

### adr

- `2026-07-27-canonical-release-pipeline-adr` - `canonical-release-pipeline` adr: `the docs and landing delivery leg of the canonical release pipeline: AWS stays for cadrumo.neve.md, docs publish is an automated release consequence, and the stale marketplace identity retires by declared supersession` | (**status:** `accepted`)

### audit

- `2026-07-27-canonical-release-pipeline-campaign-close-honesty-review-audit` - `canonical-release-pipeline` audit: `campaign close honesty review`

### exec

- `2026-07-27-canonical-release-pipeline-P01-S01` - Create the burned-version ledger as a committed data file seeded with 0.2.0 and 0.2.1, each entry carrying version, burn date, and one-line reason, loaded by a typed reader, gate: uv run --no-sync pytest dev/release/tests/test_burned_versions.py -q passes with tests covering both seeded entries and refusal of a malformed or duplicate entry
- `2026-07-27-canonical-release-pipeline-P01-S02` - Extend the destination guard into one all-destination version-identity authority checking the three PyPI projects, the v-tag and release namespace including drafts, the monotonic manifest floor, and the burned ledger, refusing with the owning destination named, gate: uv run --no-sync pytest dev/release/tests -q -k version_identity passes with one refusal case exercised per destination class plus the burned-version and floor refusals
- `2026-07-27-canonical-release-pipeline-P01-S03` - Invoke the identity authority at cohort seal time in the packaging workflow so sealing a version that is owned, burned, or not above the manifest floor refuses before any artifact uploads, gate: uv run --no-sync pytest dev/packaging/tests -q -k workflow passes with a conformance test pinning the seal job's guard invocation, full seal-refusal execution needs a CI dispatch and is flagged non-local
- `2026-07-27-canonical-release-pipeline-P01-S04` - Replace the check-pypi-only destination guard in Gate 2 with the all-destination authority, gate: uv run --no-sync pytest dev/release/tests -q -k publish_release passes with the conformance test asserting no check-pypi-only invocation remains and the Gate 2 step invokes the authority
- `2026-07-27-canonical-release-pipeline-P02-S05` - Invert the promote job's destination order to release creation with assets and docs payload, then Scoop, Homebrew, and marketplace pushes, then the PyPI upload last, gate: uv run --no-sync pytest dev/release/tests -q -k publish_release passes with the conformance test pinning PyPI as the final destination write
- `2026-07-27-canonical-release-pipeline-P02-S06` - Prove every destination step idempotent against its own prior success so a re-dispatch of the same cohort converges, using clobber or skip-existing semantics per destination, gate: uv run --no-sync pytest dev/release/tests dev/packaging/tests -q -k idempot passes over the helper functions, end-to-end re-dispatch convergence needs CI and is flagged non-local
- `2026-07-27-canonical-release-pipeline-P03-S07` - Delete the retiring upload workflow and its conformance test and sweep every reference, gate: rg -i pypi-upload across the tree returns only vault records and history, and uv run --no-sync pytest dev/release/tests -q passes clean after the deletion
- `2026-07-27-canonical-release-pipeline-P04-S08` - Declare the superseded-names axis in the generated cohort marketplace manifest, seeded with the retired aeat plugin identity, gate: uv run --no-sync pytest dev/packaging/tests -q -k marketplace passes with the generator test asserting the declaration is emitted in every generated manifest
- `2026-07-27-canonical-release-pipeline-P04-S09` - Teach the marketplace merge tool to remove a superseded entry and its subtree only where published_by matches this product or is absent, refusing a sibling-owned name identically to a takeover, gate: uv run --no-sync pytest dev/packaging/tests -q -k marketplace passes covering own-entry removal, publisher-less removal, sibling refusal, and idempotent re-run on an already-clean index
- `2026-07-27-canonical-release-pipeline-P04-S10` - Add the fail-closed publish preflight refusing while a retired name or retired-identity account metadata remains live and un-superseded in the marketplace index, with the refusal naming the supersession instruction, gate: uv run --no-sync pytest dev/packaging/tests -q -k preflight passes covering the refusal and the clean-pass cases
- `2026-07-27-canonical-release-pipeline-P05-S11` - Extend the doc-privacy gate with the cross-project identifier class, shape rules for 32-hex infrastructure ids, cloud role-identifier shapes, and owner-slash-repo slugs outside the declared reference set, plus fragment tokens for known private names, preserving the legal-attribution exemption untouched, gate: uv run --no-sync pytest dev/quality/tests/test_doc_privacy.py -q passes including a planted-violation self-test per new shape class that reds when its refusal is removed
- `2026-07-27-canonical-release-pipeline-P05-S12` - Widen the privacy scan scope from the tracked tree to tracked plus staged plus untracked-not-ignored files, gate: the same pytest invocation passes with a self-test that plants a violating untracked file in an injectable temporary repository root and asserts the gate reds, proving the extension is not tautological against the real repo state
- `2026-07-27-canonical-release-pipeline-P06-S13` - Author the docs consequence workflow triggered on release published and by dispatch, running on the self-hosted fleet, reading the deploy role from an environment-scoped variable with zero stored credentials, alerting on failure and never blocking the release, gate: a workflow conformance test pins the trigger set, runner labels, OIDC permissions, and the absence of secret literals and passes locally, live execution is BLOCKED on OP-3 and flagged non-local
- `2026-07-27-canonical-release-pipeline-P06-S15` - Codify the release runbook with the bump-first release-please step, the docs consequence, the distribution-complete tripwire, and the 0.1.0 first-version expectation, sweeping user docs where they describe the release flow, gate: uv run --no-sync pytest dev/docs/tests -m docs -q and the documented-command conformance test pass
- `2026-07-27-canonical-release-pipeline-P06-S16` - Run the fresh-context honesty review against the campaign closure summary and persist it as a vault audit with every surfaced item tracked as a new Step or formally deferred with a named follow-up, gate: the audit document exists under .vault/audit and uv run --no-sync vaultspec-core vault plan status reports no checked Step without an exec record
- `2026-07-27-canonical-release-pipeline-P07-S17` - Wire the Homebrew and Scoop generator tests into the full-CI lane as a dedicated explicit-path serial invocation of packaging/homebrew/tests and packaging/scoop/tests, honoring their serial marker with a single-worker run rather than excluding it, sized into ci-full deliberately because their real sdist and wheel builds cost minutes that the per-push budget cannot absorb, gate: uv run --no-sync pytest packaging/homebrew/tests packaging/scoop/tests -q -n0 -m serial passes locally at 14 of 14 and a lane conformance test pins the ci-full invocation covering both paths
- `2026-07-27-canonical-release-pipeline-P07-S18` - Add the lane-reachability gate asserting every test_*.py under the repository is selected by at least one declared pytest lane, computing reachability from pyproject testpaths, justfile recipes, and every workflow pytest invocation with both the path scope AND the marker expression modeled, since this incident's tests were excluded twice over, gate: uv run --no-sync pytest dev/ci/tests -q -k reachability passes and its injectable-root self-test plants an orphaned test file and asserts the gate reds
- `2026-07-27-canonical-release-pipeline-P06-S14` - Remove the CI-refusal guard from the docs publisher in the same change that binds the consequence workflow to the protected docs environment, gate: uv run --no-sync pytest dev/deploy/tests -q passes with the guard's absence asserted and the build path exercised under CI markers, deployment against the live stack is BLOCKED on OP-3 and flagged non-local

### plan

- `2026-07-27-canonical-release-pipeline-plan` - `canonical-release-pipeline` plan

### research

- `2026-07-27-canonical-release-pipeline-research` - `canonical-release-pipeline` research: `measured state of the docs, landing, and marketplace delivery surfaces`
