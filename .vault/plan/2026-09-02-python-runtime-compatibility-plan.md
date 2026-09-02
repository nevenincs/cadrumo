---
tags:
  - '#plan'
  - '#python-runtime-compatibility'
date: '2026-09-02'
tier: L2
related:
  - '[[2026-09-02-python-runtime-compatibility-adr]]'
  - '[[2026-09-02-python-runtime-compatibility-research]]'
modified: '2026-09-02'
body_schema: body-v2
body_hash: 'sha256:253d314f4bbea7bde6359b21e5960ce59f7b8d6f85378b5248bf09157aa372d3'
---

<!-- RETIRED: S33, S35, S37, S39, S41, S43, S44, S45, S46, S47, S48, S49, S50, S51, S52, S53, S54, S55, S56, S57 -->

# `python-runtime-compatibility` plan

Implement one Python 3.13-and-later source tree with an open installation floor, explicit released-runtime evidence, a rolling prerelease canary, separate source and binary dependency verdicts, and runtime testing of one immutable release cohort.

## Description

This plan executes `2026-09-02-python-runtime-compatibility-adr` using the grounding in `2026-09-02-python-runtime-compatibility-research`. It separates broad runtime compatibility from the exact `.python-version` release-builder identity and preserves existing protected CI lane contracts.

## Steps

### Phase `P01` - establish the compatibility contract

Make metadata, inventory, and release-cohort boundaries authoritative.

- [x] `P01.S01` - Change the root package floor to >=3.13 and preserve py313 static-analysis targets; `pyproject.toml`.
- [x] `P01.S02` - Regenerate lock metadata without dependency upgrades; `uv.lock`.
- [x] `P01.S03` - Add explicit stable and prerelease runtime records and classifier eligibility; `dev/ci/python-runtime-matrix.json`.
- [x] `P01.S04` - Parse and validate the runtime inventory and emit GitHub matrix JSON; `dev/ci/python_runtime_matrix.py`.
- [x] `P01.S05` - Add detector-teeth tests for runtime inventory gaps duplicates and invalid states; `dev/ci/tests/test_python_runtime_matrix.py`.
- [x] `P01.S06` - Replace the stale Python ceiling assertion with the open-floor policy; `dev/audit/security.py`.
- [x] `P01.S07` - Update security-audit expectations for the open-ended floor; `dev/audit/tests/test_security.py`.
- [x] `P01.S08` - Guard the exact CPython release-builder identity; `dev/packaging/tests/test_release_cohort.py`.

### Phase `P02` - harden dev and src runtime compatibility

Keep one annotation model and detect APIs removed or deprecated across the supported CPython range.

- [x] `P02.S09` - Add an AST compatibility census for removed and deprecated Python APIs; `dev/quality/python_compatibility_scan.py`.
- [x] `P02.S10` - Add representative-defect tests for the compatibility census; `dev/quality/tests/test_python_compatibility_scan.py`.
- [x] `P02.S11` - Harden public annotation resolution and forward-reference behavior; `src/cadrumo/application/modelo/workspace_manifest.py`.
- [x] `P02.S12` - Exercise annotation contracts through the workspace-manifest path; `src/cadrumo/application/modelo/tests/test_workspace_manifest.py`.
- [x] `P02.S13` - Harden dynamic wizard signatures against annotation representation changes; `src/cadrumo/application/wizard/commands.py`.
- [x] `P02.S14` - Test dynamic signatures type hints metadata and CLI discovery; `src/cadrumo/application/wizard/tests/test_commands_helpers.py`.
- [x] `P02.S15` - Compile every dev and src module against the oldest supported grammar; `dev/tests/test_every_source_file_parses.py`.
- [x] `P02.S16` - Enforce annotations as the sole project future directive; `dev/tests/test_import_hygiene_scan.py`.
- [x] `P02.S60` - Replace production TOML reading with the Python standard library; `src/cadrumo/core/toml.py`.
- [x] `P02.S61` - Prove standard-library TOML parsing preserves the public error contract; `src/cadrumo/core/tests/test_toml.py`.

### Phase `P03` - produce attributable source and binary evidence

Create one reusable runner and bind its evidence to the tested artifact and runtime.

- [x] `P03.S17` - Implement isolated source and binary compatibility probes with JSON evidence; `dev/ci/python_runtime_compatibility.py`.
- [x] `P03.S18` - Test mode separation lock binding digest binding and missing-wheel refusal; `dev/ci/tests/test_python_runtime_compatibility.py`.
- [x] `P03.S19` - Extend distribution evidence with runtime stability and installation outcomes; `dev/packaging/evidence.py`.
- [x] `P03.S20` - Test source versus binary evidence and foreign cohort refusal; `dev/packaging/tests/test_evidence.py`.
- [x] `P03.S21` - Reuse installed-wheel isolation for selected target interpreters; `dev/packaging/_smoke_common.py`.
- [x] `P03.S22` - Verify smoke acceptance removes checkout imports and ambient executables; `dev/packaging/tests/test_smoke_core_env.py`.

### Phase `P04` - add the dedicated rolling workflow

Add a separately verdictable workflow without expanding protected CI or release-cohort builders.

- [x] `P04.S23` - Add stable and next source and binary compatibility matrix jobs; `.github/workflows/python-runtime-compatibility.yml`.
- [x] `P04.S24` - Gate workflow inventory source mode separation skips warnings and digests; `dev/ci/tests/test_python_runtime_compatibility_workflow.py`.
- [x] `P04.S25` - Permit only the dedicated runtime matrix while preserving exact-pin lanes; `dev/ci/tests/test_python_version_pin.py`.
- [x] `P04.S26` - Enroll the compatibility workflow in change-class and fork-safety invariants; `dev/ci/tests/test_change_class_tiers.py`.
- [x] `P04.S27` - Verify workflow Python calls use repository module entry points; `dev/ci/tests/test_workflow_tool_invocation.py`.
- [x] `P04.S28` - Preserve protected packaging-smoke single-build behavior; `dev/packaging/tests/test_packaging_smoke_workflow.py`.
- [x] `P04.S29` - Preserve protected quick-packaging single-runtime behavior; `dev/packaging/tests/test_packaging_quick_workflow.py`.
- [x] `P04.S58` - Invoke clean release-cohort construction through its package module; `dev/packaging/release_cohort.py`.
- [x] `P04.S59` - Prove clean release-cohort subprocess imports remain package-correct; `dev/packaging/tests/test_release_cohort.py`.
- [x] `P04.S62` - Scope hash enforcement without rejecting locally built cohort artifacts; `dev/packaging/release_cohort.py`.
- [x] `P04.S63` - Prove clean cohort construction accepts digest-bound local wheels; `dev/packaging/tests/test_release_cohort.py`.

### Phase `P05` - align stable metadata release gates and documentation

Make stable support claims only after their blocking evidence passes.

- [x] `P05.S30` - Add classifiers only for stable runtimes proven by the matrix; `pyproject.toml`.
- [x] `P05.S31` - Align manuals companion classifiers with stable runtime evidence; `packaging/cadrumo_data_manuals/pyproject.toml`.
- [x] `P05.S32` - Align official-data companion classifiers with stable runtime evidence; `packaging/cadrumo_data_official/pyproject.toml`.
- [x] `P05.S34` - Enforce root and companion classifier parity and prerelease exclusion; `dev/packaging/tests/test_classifier_parity.py`.
- [x] `P05.S36` - Test sealed release artifacts across supported stable runtimes; `.github/workflows/publish.yml`.
- [x] `P05.S38` - Document local runtime selection and source versus binary evidence; `CONTRIBUTING.md`.
- [x] `P05.S40` - Document final-runtime promotion and classifier evidence; `RELEASING.md`.
- [x] `P05.S42` - Add an inventory-driven local compatibility command; `justfile`.
- [x] `P05.S64` - Promote 3.14 classifier eligibility after source binary and artifact evidence; `dev/ci/python-runtime-matrix.json`.

### Phase `P06` - close final compatibility review findings

Make every selected runtime carry focused behavioral and MCP evidence, keep the future-directive policy in a blocking compatibility lane, and classify binary resolver failures precisely.

- [ ] `P06.S65` - Run a focused behavioral test set under the selected target interpreter and bind its results to the compatibility verdict; `dev/ci/python_runtime_compatibility.py`.
- [ ] `P06.S66` - Smoke the installed cadrumo-mcp entry point and import contract in every compatibility mode; `dev/ci/python_runtime_compatibility.py`.
- [ ] `P06.S67` - Wire the future-directive AST policy into the blocking compatibility workflow; `.github/workflows/python-runtime-compatibility.yml`.
- [ ] `P06.S68` - Classify binary missing-wheel failures only from resolver-specific diagnostics; `dev/ci/python_runtime_compatibility.py`.
- [x] `P06.S69` - Align the prerelease selector with the provisionable rolling minor; `dev/ci/python-runtime-matrix.json`.

## Parallelization

The metadata and inventory work in P01 and the source compatibility work in P02 may proceed concurrently when file ownership is disjoint. P03 depends on the P01 inventory and P02 runtime contracts. P04 depends on P03. P05 follows successful stable-runtime evidence. `pyproject.toml` has one owner across its two steps, and the existing dirty worktree must be re-read before every edit.

## Verification

The open floor and regenerated lock must validate without a Python upper bound. The inventory must prove every released CPython minor from 3.13 and exactly one next prerelease. Stable rows must exercise source, binary, dependency, import, CLI, focused-test, and immutable-artifact paths. Prerelease failures and missing wheels remain attributable and never become skips. Annotation behavior remains consistent, existing protected lanes retain the exact 3.13.11 builder, classifier claims match proven stable rows, focused and broad quality gates pass, and mandatory code review reports no high-severity finding.
