---
tags:
  - '#plan'
  - '#gate-60-minutes'
date: '2026-11-25'
tier: L1
related:
  - '[[2026-11-25-gate-60-minutes-adr]]'
  - '[[2026-11-25-gate-60-minutes-research]]'
modified: '2026-11-25'
body_schema: body-v2
body_hash: 'sha256:a4914edf86508e91ddbf8991c9b2df6219ba03cb89917f489f849c3b53922b27'
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
     Replace gate-60-minutes with a kebab-case feature tag, e.g. #foo-bar.
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

# `gate-60-minutes` plan

The complete local gate, every population and static check, in 60 minutes or less on this machine with no loss of real coverage.

## Description

Approved 2026-11-25. Basis: the operator's order of 2026-11-25 (`.tmp/2026-11-25-evidence/BRIEF-GATE-60.md`), which instructs the gate lead to write this plan, delegate its execution and measure a full gate.

Decision coverage: `2026-11-25-gate-60-minutes-adr` governs every Step; its evidence is `2026-11-25-gate-60-minutes-research`. No other new decision is involved. S09 is limited to the three reductions the ADR names.

Projected wall time for the finished gate on a quiet machine, against a loaded baseline of 3 h 39 min for the test lanes plus 2 h 41 min for the measured static steps:

| Change | Step | Effect on gate wall time |
| --- | --- | --- |
| Concurrent nodes under one budget instead of an eleven-step queue at six workers | S01, S02 | static, documentation and test nodes overlap; the gate is as long as its longest chain, not the sum |
| Harness and sequence corpus once instead of three times | S02 | removes about 36 min of serial work twice over |
| Duration-balanced shards, tail files spread by test | S03 | no node waits on a single 20 minute file |
| Registry loaded, not compiled, per worker; validation record kept | S04 | removes 41 to 58 s per worker per invocation |
| One strict documentation build, wider sequence pool | S05 | documentation chain to about 20 min, golden check to about 12 to 15 min |
| Static checks concurrent, clean verdicts reused | S06 | static chain from 41 min to about 8 min, less when inputs are unchanged |
| Rendering capture examined, no change | S07 | none: the two digests hash different serialisations by contract |
| Hoisted per-revision work, persona replay reuse | S08 | about 1,400 summed seconds |
| Three recorded reductions | S09 | about 1,800 summed seconds |
| One distribution build feeds the wheel tests | S10 | removes repeated wheel builds |

Longest expected chain after all Steps: prerequisites 3 min, then test shards 40 to 50 min in parallel with documentation and static nodes, then the benchmark node 4 min: 45 to 55 min. These figures rest on loaded measurements and are confirmed or corrected by S11.

<!-- First line after approval: `Approved yyyy-mm-dd`, written by the
orchestrator after establishing scoped authorization, including an explicit
advance authorization. Record its basis; ask only when it is absent. Then briefly describe the proposed work.
Reference `{adr}`s, `{research}`, `{reference}`. Supporting documentation
must be read when relevant. State the decision coverage assessment; when no
costly decision is involved and no ADR governs, say so. With several ADRs,
map their scope to Steps at L1 or the relevant containers at higher tiers. -->

## Steps

- [x] `S01` - Build the concurrent gate runner: node graph with ordering and exclusive resources, one global worker budget, continue past red, separate parallel and serial nodes, tree digest at start and end, durable per-node record with JUnit and per-file timing aggregation; `dev/test_runs`.
- [ ] `S02` - Compose gate-local on the runner so every current population runs exactly once: one harness run, sequence check skipped inside the gate docs build, prerequisites once, CPU-budget benchmarks last and alone; `justfile`.
- [ ] `S03` - Balance shards by recorded per-file seconds with size fallback and distribute tail-setting files across workers by test; `dev/ci/gate_shards.py`.
- [x] `S04` - Load the compiled bundled registry from a digest-keyed disk copy proven equal to a fresh compile, and make the clean-validation record survive process exit; `dev/registry`.
- [x] `S05` - Compile the documentation strictly once per gate with a digest-keyed record read by the strict-build test, size the sequence pool to the budget, split the golden check per sequence, and key the parent page skip on the child environment; `dev/docs`.
- [x] `S06` - Run the static checks concurrently and reuse a clean verdict when the content-digest input key matches, keeping each positive control under the same key; `dev/quality`.
- [x] `S07` - Establish whether the rendering capture serialises the registry payload twice; finding: it does not (the two digests hash two different serialisations by contract and the payload is not a function of generation, modelo and revision), so no product change is made; `src/cadrumo/domain/modelos/calculation_revision_rendering.py`.
- [x] `S08` - Hoist per-revision work in the work-form answer tests to module scope, use persona replay reuse where a test needs no fresh replay, and add the producing-source digest to the sealed-world key; `src/cadrumo/adapters/persistence/profile/tests`.
- [ ] `S09` - Apply the three recorded coverage reductions after showing the retained tests assert every claim of the removed cases; `dev/acceptance/iva/tests`.
- [ ] `S10` - Seed the shared wheel cohort from the one gate distribution build and move the uncached wheel-building tests onto it; `dev/packaging`.
- [ ] `S11` - Measure a full gate on a still tree and a quiet machine, record per-node times against the 60 minute target, and write the status report; `.tmp/2026-11-25-evidence/GATE60-STATUS.md`.

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

S01, S04, S05, S06, S07 and S08 run concurrently; their write ownership is disjoint: `dev/test_runs` (S01), `dev/registry` (S04), `dev/docs` (S05), `dev/quality` (S06), the rendering owner under `src/cadrumo` (S07), and test files under `src/cadrumo` (S08). S02 and S03 follow S01 and own `justfile` and `dev/ci`. S09 and S10 follow S08 and S02. S11 is last. All work is in the root checkout on owned hunks; each worker stages only its own files, runs focused tests at two workers, and uses no attach profiler. Commits are serialised by the lead.

<!-- State which Steps, Phases, or Waves can be executed in parallel and
which carry hard ordering. At `L1` and `L2`, parallelism is decided
per-Step or per-Phase. At `L3` and `L4`, Waves are sequenced by
default (one Wave must land before the next can begin); Phases
within a single Wave may be parallelized when they share no hard
interdependency. -->

## Verification

- A full gate on a named `feature/tui` head, on a quiet machine with an unchanged tree, completes in 60 minutes or less, with the per-node record showing every population `gate-local` ran before this plan.
- The count of collected tests per population before and after is recorded; every difference is explained by S09 or by a moved file.
- Each cache or reused verdict has a test that changes one declared input and observes a full rerun, and each scanning gate's positive control runs under the same key.
- The compiled-registry copy passes a typed equivalence check against a fresh compile; rendering digests are byte-identical before and after S07.
- Focused tests, `just check-style`, `just check-format`, `just check-types` and `just check-import-boundaries` pass on touched files; a protocol change runs `python -m dev.quality.types --full`.
- Reds that pre-date this plan are reported separately from regressions.

<!-- State the mission success criteria for this plan. Each criterion
should be a verifiable check (test passes, surface conforms,
reviewer signs off) rather than a free-form assertion.

The plan is complete when every Step is closed (`- [x]`) and the final
cohesive review passes. At `L4`, the Epic-completion check additionally requires
the declared project-management association to report the Epic
complete.

Review follows the vaultspec system section. L1 has no Phase close;
coincident plan-close and handoff gates share one integrated review. -->
