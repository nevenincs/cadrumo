---
tags:
  - '#plan'
  - '#test-suite-budget'
date: '2026-10-30'
tier: L1
related:
  - '[[2026-08-14-test-harness-sanity-successor-adr]]'
modified: '2026-10-30'
body_schema: body-v2
body_hash: 'sha256:e2d888e4ea35ef26b29b7bcce89c0d80d679873c34c53b6e9ead54ee1b0d33ff'
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
     Replace test-suite-budget with a kebab-case feature tag, e.g. #foo-bar.
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

# `test-suite-budget` plan

<!-- One-line headline summary plan. -->

## Description

Approved 2026-10-30

The operator asked to cut the full test lane from about 3.5 hours to 30 minutes, reduce the suite to what it needs, and remove all copy-paste from the test trees. That request authorizes these Steps. Coverage: `2026-08-14-test-harness-sanity-successor-adr` governs fixture ownership and worker width, and S08 amends its width.

Measured baseline, 2026-10-30, on a shared loaded box: 67,703 collected tests in 6,068 files and 76,213 worker-seconds. The phase split is call 87.7%, setup 11.4%, teardown 0.9%. Tests under 0.05s number 44,669 and total 359s; the 6,070 tests over 2s hold 92% of the time. The 30-minute target means 21,600 worker-seconds at 12 workers.

Speed comes first from removing repeated work in the slowest tests. A removal needs evidence that nothing the test proves is lost; official examples, independent oracles and refusal paths are not cut on overlap alone.

## Steps

- [x] `S01` - Compose the conformance runtime once per worker instead of per case: registered-executor conformance and subject binding (7,100s); `src/cadrumo/entrypoints/tests/registered_executor_case_support.py`.
- [ ] `S02` - Share the remaining per-case composition across the actor-by-frontend and parity families (about 3,500s); `src/cadrumo/entrypoints/tests`.
- [ ] `S03` - Reuse one compiled tree across generated-export trees and inheritance cases (2,500s); `dev/registry/pipeline/tests`.
- [ ] `S04` - Replace per-defect real-gate launches in the import quality gate with one shared baseline (2,255s); `dev/tests/test_import_quality_gate.py`.
- [ ] `S05` - Bound TUI sequence walks and workbench acceptance to one composed app per module (2,800s); `dev/tui/harness/tests, src/cadrumo/entrypoints/tui/tests`.
- [ ] `S06` - Reduce the per-command CPU floor and repeated calculation cost on the product CLI path; `src/cadrumo_client, src/cadrumo_runtime, src/cadrumo/application/modelo`.
- [ ] `S07` - Stop seeding test state through whole CLI commands where the command is not the subject; `src/cadrumo_runtime/host/tests/frontend/cli, src/cadrumo/entrypoints/tests/profile_persistence`.
- [ ] `S08` - Raise the default worker width to the measured best and amend the worker decision; `src/cadrumo/tests/worker_count_hook.py`.
- [ ] `S09` - Remove whole-function and token-level clones across test trees; `src, dev test trees`.
- [ ] `S10` - Prune redundant tests by per-test coverage and mutation evidence on critical modules; `src, dev test trees`.
- [ ] `S11` - Add a lane time budget and per-test ceiling so the suite cannot drift back; `justfile, dev/test_runs`.

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

S02, S03, S04 and S05 run concurrently with disjoint write scopes: S02 `src/cadrumo/entrypoints/tests` plus `dev/operation_contract_manifest/tests`; S03 `dev/registry`; S04 `dev/tests`, `dev/docs/tests`, `dev/locales/tests` and `dev/packaging/tests`; S05 `dev/tui` and `src/cadrumo/entrypoints/tui`. Workers commit their own paths. The orchestrator serializes ledger rows and Step closure. S08 and S10 wait until these finish, because width and pruning measurements need a stable suite.

## Verification

<!-- State the mission success criteria for this plan. Each criterion
should be a verifiable check (test passes, surface conforms,
reviewer signs off) rather than a free-form assertion.

The plan is complete when every Step is closed (`- [x]`) and the final
cohesive review passes. At `L4`, the Epic-completion check additionally requires
the declared project-management association to report the Epic
complete.

Review follows the vaultspec system section. L1 has no Phase close;
coincident plan-close and handoff gates share one integrated review. -->
