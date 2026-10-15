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
modified: '2026-10-15'
body_schema: body-v2
body_hash: 'sha256:f25b5a2cb6267f74955b1dc5e7bf4ad75200c56d5c3c6b65984f8a84704f257c'
---

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the
       related: field above.
     - The related: field carries governing ADRs, if any.
       Steps inherit their evidence transitively. Direct supporting
       evidence links are optional; per-row footers do not exist.
     - NEVER use [[wiki-links]] or markdown links in the
       document body. -->

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #plan) and one feature tag.
     Replace unit-suite-repair with a kebab-case feature tag, e.g. #foo-bar.
     Exactly these two tags are allowed; do not append additional tags.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     tier is mandatory for new plans. Allowed: L1, L2, L3, L4.
     L1 = Steps only. L2 = Phases above Steps. L3 = Waves above
     Phases above Steps. L4 = Epic above Waves above Phases above
     Steps; PM association required. Pre-existing plans without this
     field default to L2.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'. The related field
     carries governing ADRs; Steps inherit their evidence transitively.
     Direct supporting evidence links are optional. A decision-free plan
     records its coverage assessment in the Description.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->


<!-- HIERARCHY AND TIERS:
     Epic > Wave > Phase > Step. Step is the canonical leaf-row
     noun. Execution artifact: the plan's ledger.
     Tier is declared in frontmatter as tier: L1/L2/L3/L4
     (mandatory for new plans; pre-existing plans without the
     field default to L2 until `vaultspec-core vault check all --fix` adds it).
     The tier selects containers:
       L1 = Steps only.
       L2 = Phases above Steps.
       L3 = Waves above Phases above Steps.
       L4 = Epic above Waves above Phases above Steps; MUST declare
            a project-management association in the Epic intent
            block prose.
     Select the smallest hierarchy that clarifies coordination:
       L1 = a flat sequence of cohesive revisions, including broad changes.
       L2 = Phases clarify groups of Steps.
       L3 = Waves clarify dependencies between groups of Phases.
       L4 = an Epic coordinates a program with external tracking.
     Duration, file count, package count, or short parallel work alone
     never requires a higher tier.
     Between two tiers take the smaller and promote later.
     Writer never invents containers to qualify a tier. -->

<!-- IDENTIFIERS AND ROW CONTRACT:
     S##, P##, W## are flat, per-document, append-only, immutable.
     Promotion adds containers without renumbering. Gaps are not
     reused.
     Display paths are computed from current grouping:
       Step path:    L1 S##   L2 P##.S##   L3/L4 W##.P##.S##
       Phase heading:        L2 P##       L3/L4 W##.P##
       Wave heading:                      L3/L4 W##
     Row format:
       - [ ] `<display-path>` - imperative-verb action; `path/to/file`.
     Two-state checkboxes only ([ ] open, [x] closed). No per-row
     reference footers; wiki-links and markdown links are forbidden
     in plan body. Authorizing documents go in the plan's `related:`
     frontmatter once.
     ASCII spaced hyphens everywhere; em-dash (U+2014) and en-dash
     (U+2013) are forbidden. Step rows within a Phase are
     contiguous. -->

<!-- COHESIVE GRANULARITY:
     One Step is one cohesive, verifiable commit. Coordinated repeated edits
     may share a row when scope and verification are explicit. Separate
     unrelated outcomes. Name the bounded files or area, expected creations,
     and intended result; avoid unspecified catch-all work. -->

<!-- VAULTSPEC-CORE VAULT PLAN CLI:
     The `vaultspec-core vault plan` CLI is the canonical surface for
     structural manipulation of this plan document. Writers and
     executors MUST use `vaultspec-core vault plan step add/insert/move/
     remove/check/uncheck/toggle/edit`,
     `vaultspec-core vault plan phase add/move/remove/edit`,
     `vaultspec-core vault plan wave add/move/remove/edit`,
     `vaultspec-core vault plan epic intent`, and
     `vaultspec-core vault plan tier promote/demote` for every
     identifier-affecting change; the `plan_edit` and `plan_progress`
     MCP tools reach the Step verbs only, and the above-Step verbs run
     through the CLI. Hand edits are forbidden and
     flagged by `vaultspec-core vault plan check`; canonical-identifier
     preservation is guaranteed only when a verb performs the mutation. Run
     `vaultspec-core vault plan --help` for the full subcommand
     surface. -->

# `unit-suite-repair` plan

<!-- One-line headline summary plan. -->

## Description

Approved 2026-10-15

Authorization: the user requested running all unit tests and fixing all issues. Preserve the earlier instruction prohibiting exceptions and suppressions. Restore real behavior and complete collection; do not weaken assertions, add skips or xfails, remove tests merely to obtain green results, or overwrite concurrent work.

The accepted import-centralization, test-harness-sanity and test-topology decisions govern canonical definitions, product/runtime responsibilities, fixture lifetime, collection integrity and complete verification. No new costly decision is required for ordinary defect repairs within these commitments. Escalate a newly uncovered costly choice with evidence rather than silently changing authority. Existing source repair and type-check plans retain their own history and ownership.

S01 covers all five configured product Python roots, including application calculations and registry calculation tests omitted by the usual test-unit recipe. S02 covers dev, native/tests and packaging/homebrew/tests. S03 covers native Rust unit cases through existing CMake wrappers and frontend Node unit suites. S04 integrates repaired scopes, the configured static checks, capability inventory and final review. Test the current source before repairing an older diagnostic because this worktree contains concurrent changes.

## Steps

- [x] `S01` - Repair product unit test failures while preserving package and fixture ownership; `src/cadrumo, src/cadrumo_client, src/cadrumo_runtime, src/cadrumo_harness, src/cadrumo_agent_service`.
- [ ] `S02` - Repair developer and distribution tooling unit failures at their defining owners; `dev, justfile, pyproject.toml, .github/workflows/release.yml, native/cmake/Packaging.cmake, native/cmake/ReleaseVerification.cmake, native/tests, packaging/homebrew/tests, docs/conf.py and docs/api/index.md canonical five-package API discovery and reference enrollment, docs environment reference and agent connection guide with translations and executable sequences, identity-and-naming page and Spanish Catalan Hungarian catalogues for proven reversible encoding and current-message repairs, canonical derived corpus extraction sidecar for real-decreto-ley-23-2026-art-1.html without raw HTML changes, modelos126 and128 canonical export targets, modelo303 revision2022 and modelo322 revision2008-2022 and modelo390 revision2022 constructs consolidation without semantic change, modelo303 revision2026-hasta-01-y-1t row112 evidence-backed not-on-form disposition for existing zero-only carrier without ledger exceptions or active continuity, canonical authority publication to ignored .authority, source-only API docstrings in src/cadrumo/adapters/persistence/storage/custody/kdf_supervision.py and src/cadrumo/core/request_faults.py and src/cadrumo/application/workflow/persistence.py and src/cadrumo_client/commands/secure_input.py`.
- [x] `S03` - Repair native Rust and frontend unit failures through their existing build contracts; `native Rust crates and native/desktop/frontend unit test modules`.
- [ ] `S04` - Verify the complete unit populations and integrated repairs without weakened gates; `full product and tooling unit selectors, available native unit tests, configured lint format and type checks, capability inventory and repair audit`.

<!-- The plan's tier (declared in frontmatter as `tier: L1`, `L2`, `L3`, or
`L4`) determines the structure under this section:

- `L1`: a flat list of Step rows (no Phase, Wave, or Epic).
- `L2`: one or more `### Phase` blocks each containing Step rows.
- `L3`: one or more `## Wave` blocks each containing Phase blocks.
- `L4`: a `## Epic intent` block, followed by Wave blocks. -->

<!-- Replace this scaffold with the tier-appropriate structure for your plan.
Format examples for each block type are embedded below as commented
templates. -->

<!-- Progress is recorded through the plan verbs (`plan_progress`,
     `vaultspec-core vault plan step check`), one Step at a time. -->

<!-- PHASE BLOCK FORMAT (L2, L3, L4):
     ### Phase `P02` - rewrite the writer-agent contract

     One sentence stating what this Phase delivers.

     - [ ] `P02.S01` - imperative-verb action; `path/to/file`.
     - [ ] `P02.S02` - imperative-verb action; `path/to/file`.

     At L3/L4 the Phase heading uses the ancestor-aware path
     (### Phase `W01.P02` - ...). The intent sentence is mandatory. -->

<!-- WAVE BLOCK FORMAT (L3, L4):
     ## Wave `W01` - language-only convention rollout

     One paragraph stating what this Wave delivers, which downstream
     Wave depends on it, and which authorizing documents back it.

     ### Phase `W01.P01` - ...
     ### Phase `W01.P02` - ...

     The Wave intent paragraph is mandatory. -->

<!-- EPIC INTENT BLOCK FORMAT (L4 only):
     ## Epic intent

     One paragraph stating the strategic goal, the external project-
     management association (milestone name, project board identifier,
     roadmap entry), the timeline horizon, and the teams or agents
     involved.

     For user-requested coordination across the program and its tracker,
     vaultspec-projectmanager owns that context and assignments; this
     plan remains the home of implementation sequencing.

     ## Wave `W01` - ...
     ## Wave `W02` - ...

     The ## Epic intent block is mandatory at L4 and absent at L1, L2,
     L3. The plan title (the level-one # heading at the top of the
     document) is the Epic title; no separate Epic heading is emitted. -->

## Parallelization

Luna max python_lint owns the S01 product unit baseline and assigned disjoint product repairs. Luna max format_checks owns the S02 developer-tool unit baseline and assigned disjoint tooling repairs. Luna max native_frontend_lint owns S03 native/frontend unit discovery, execution and assigned disjoint native/frontend repairs. These Steps may run concurrently with separate outputs and no overlapping source writes. Initial runs are read-only until root assigns concrete failure groups. Root serializes shared metadata, cross-owner fixes and S04 integration; workers never stage, commit or revert another writer's changes.

Initial full runs use four explicit xdist workers per Python population. Baseline and rerun logs live under .logs/unit-repair-20261015. Preserve the configured capability boundaries and report unavailable or held-out unit populations explicitly. Serialize CMake build and CTest operations within each shared binary directory.

## Verification

Retain full verbose output and actual final exit status for the product and developer unit runs. Product scope uses all five configured src roots and the existing offline unit marker expression, excludes only the dedicated child-pytest integration harness and includes calculation paths. Developer scope uses dev, native/tests and packaging/homebrew/tests with the same unit capability expression. Inventory units held out by capability policy and execute available host-supported populations separately; distinguish unavailable prerequisites from passing tests.

Reproduce each failing behavior at its real owner before repair. Run focused success and refusal controls, preserve independent expectations and canonical ownership, then rerun the complete affected unit population. Native Rust units use configured CMake/Cargo wrappers and generated contracts; frontend units use their declared Node test runner. Do not use a whole package build as a substitute for a unit verdict.

Finish with configured lint, formatting and type checks plus the integrated review. Report actual failing checks and missing prerequisites without exceptions, suppressions or widened exclusions. Root owns final verification and the rolling repair audit. Preserve pre-existing source and index edits; stage only independently reviewable owned changes when a safe commit boundary exists.
