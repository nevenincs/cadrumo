---
tags:
  - '#plan'
  - '#unit-suite-repair'
date: '2026-10-15'
tier: L1
related:
  - '[[2026-07-01-import-centralization-adr]]'
  - '[[2026-08-14-test-harness-sanity-successor-adr]]'
  - '[[2026-06-05-test-topology-refactor-adr]]'
  - '[[2026-10-15-native-package-ci-adr]]'
modified: '2026-10-17'
body_schema: body-v2
body_hash: 'sha256:2fc1bce71b1f6c76c3208eb570455e70fef4586117718d91e76a9e66794090ab'
---

# `unit-suite-repair` plan

## Description

Approved 2026-10-15

Authorization: the user requested running all unit tests and fixing all issues. Preserve the earlier instruction prohibiting exceptions and suppressions. Restore real behavior and complete collection; do not weaken assertions, add skips or xfails, remove tests merely to obtain green results, or overwrite concurrent work.

The accepted import-centralization, test-harness-sanity and test-topology decisions govern canonical definitions, product/runtime responsibilities, fixture lifetime, collection integrity and complete verification. No new costly decision is required for ordinary defect repairs within these commitments. Escalate a newly uncovered costly choice with evidence rather than silently changing authority. Existing source repair and type-check plans retain their own history and ownership.

S01 covers all five configured product Python roots, including application calculations and registry calculation tests omitted by the usual test-unit recipe. S02 covers dev, native/tests and packaging/homebrew/tests. S03 covers native Rust unit cases through existing CMake wrappers and frontend Node unit suites. S04 integrates repaired scopes, the configured static checks, capability inventory and final review. Test the current source before repairing an older diagnostic because this worktree contains concurrent changes.

## Steps

- [x] `S01` - Repair product unit test failures while preserving package and fixture ownership; `src/cadrumo, src/cadrumo_client, src/cadrumo_runtime, src/cadrumo_harness, src/cadrumo_agent_service`.
- [x] `S02` - Repair developer and distribution tooling unit failures at their defining owners; `dev, justfile, pyproject.toml, .github/workflows/release.yml, native/cmake/Packaging.cmake, native/cmake/ReleaseVerification.cmake, native/tests, packaging/homebrew/tests, docs/conf.py and docs/api/index.md canonical five-package API discovery and reference enrollment, docs environment reference and agent connection guide with translations and executable sequences, identity-and-naming page and Spanish Catalan Hungarian catalogues for proven reversible encoding and current-message repairs, canonical derived corpus extraction sidecar for real-decreto-ley-23-2026-art-1.html without raw HTML changes, modelos126 and128 canonical export targets, modelo303 revision2022 and modelo322 revision2008-2022 and modelo390 revision2022 constructs consolidation without semantic change, modelo303 revision2026-hasta-01-y-1t row112 evidence-backed not-on-form disposition for existing zero-only carrier without ledger exceptions or active continuity, canonical authority publication to ignored .authority, source-only API docstrings in src/cadrumo/adapters/persistence/storage/custody/kdf_supervision.py and src/cadrumo/core/request_faults.py and src/cadrumo/application/workflow/persistence.py and src/cadrumo_client/commands/secure_input.py and src/cadrumo/core/text_bounds.py`.
- [x] `S03` - Repair native Rust and frontend unit failures through their existing build contracts; `native Rust crates and native/desktop/frontend unit test modules`.
- [x] `S04` - Verify the complete unit populations and integrated repairs without weakened gates; `full product and tooling unit selectors, available native unit tests, configured lint format and type checks, capability inventory and repair audit, final verification at isolated unit-repair-proof-20261015 checkpoint155f4d7f6520210c892b79512caec8e18bed4630 plus recorded final API documentation overlay while later concurrent authentication localization and launch-environment feature work remains outside this repair boundary`.

## Parallelization

Luna max python_lint owns the S01 product unit baseline and assigned disjoint product repairs. Luna max format_checks owns the S02 developer-tool unit baseline and assigned disjoint tooling repairs. Luna max native_frontend_lint owns S03 native/frontend unit discovery, execution and assigned disjoint native/frontend repairs. These Steps may run concurrently with separate outputs and no overlapping source writes. Initial runs are read-only until root assigns concrete failure groups. Root serializes shared metadata, cross-owner fixes and S04 integration; workers never stage, commit or revert another writer's changes.

Initial full runs use four explicit xdist workers per Python population. Baseline and rerun logs live under .logs/unit-repair-20261015. Preserve the configured capability boundaries and report unavailable or held-out unit populations explicitly. Serialize CMake build and CTest operations within each shared binary directory.

## Verification

Retain full verbose output and actual final exit status for the product and developer unit runs. Product scope uses all five configured src roots and the existing offline unit marker expression, excludes only the dedicated child-pytest integration harness and includes calculation paths. Developer scope uses dev, native/tests and packaging/homebrew/tests with the same unit capability expression. Inventory units held out by capability policy and execute available host-supported populations separately; distinguish unavailable prerequisites from passing tests.

Reproduce each failing behavior at its real owner before repair. Run focused success and refusal controls, preserve independent expectations and canonical ownership, then rerun the complete affected unit population. Native Rust units use configured CMake/Cargo wrappers and generated contracts; frontend units use their declared Node test runner. Do not use a whole package build as a substitute for a unit verdict.

Finish with configured lint, formatting and type checks plus the integrated review. Report actual failing checks and missing prerequisites without exceptions, suppressions or widened exclusions. Root owns final verification and the rolling repair audit. Preserve pre-existing source and index edits; stage only independently reviewable owned changes when a safe commit boundary exists.
