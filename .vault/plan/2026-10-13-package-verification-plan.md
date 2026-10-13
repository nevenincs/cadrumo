---
tags:
  - '#plan'
  - '#package-verification'
date: '2026-10-13'
tier: L1
related:
  - '[[2026-10-13-package-verification-adr]]'
  - '[[2026-10-13-native-agent-adr]]'
  - '[[2026-10-12-live-agent-evaluation-adr]]'
  - '[[2026-10-13-desktop-agent-host-live-lane-adr]]'
  - '[[2026-10-13-canonical-environment-application-internals-adr]]'
modified: '2026-10-13'
body_schema: body-v2
body_hash: 'sha256:aa4deef434b5fa9c2b840fc8d5c5a733b3556d009bc6e0624e52b81d58ebc949'
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
     Replace package-verification with a kebab-case feature tag, e.g. #foo-bar.
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

# `package-verification` plan

Hold application-level verification to the CMake package and retire the lanes and paths that diverge from it.

## Description

Approved 2026-10-13 on the owner's first-hand "approved, execute" for this plan.

Governing decision: `2026-10-13-package-verification-adr`, accepted 2026-10-13. Under it, application-level process proofs run only against `stage/<Config>/app`. Lanes that diverge are repointed or removed, and nothing is built for verification alone. The ADR's amendments are already applied to `2026-10-13-native-agent-adr` (S02), `2026-10-12-live-agent-evaluation-adr` (scope note only) and `2026-10-13-desktop-agent-host-live-lane-adr` (S04). No further costly decision is involved.

Step mapping:
- S01 is routine dead-code removal under the owner's cleanup direction. Each item is confirmed by grep and by the zero-target reachability and usage gates before it is deleted.
- S02 implements the native-agent amendment.
- S03 and S05 implement the ADR's constraint 3 and its `agent_live.py` outline.
- S04 implements the constraint against parallel paths and the live-lane revision.

Dependencies outside this plan:
- S02, S04 and S05 need a packaged host that passes the agent its environment. That is `2026-10-13-canonical-environment-application-internals-adr`, which is proposed and owned by tui-ee, with preference B forwarded to it.
- S05 also needs CADRUMO-AGENT-CODE to commit the untracked agent files, and to record the proof in `providers/lane_admission.py`.
- This plan makes no commit in cadrumo-agent.

## Steps

- [x] `S01` - Remove the dead dev tooling the sweep confirms: the uninvoked pytest shard plugin, per-file ignores for missing modules, references to the absent no-skip gate, and dev/audit screens no recipe runs, updating the recipe and lane policing tests in the same change; `dev/quality/shard.py`.
- [ ] `S02` - Extend the bundle.agent CTest probe to launch the bundled agent the way the runtime does, wait for its ready line and stop it; `native/tests/agent_smoke.py`.
- [ ] `S03` - Repoint the agent live lane onto the staged package: drop the checkout option and run the staged interpreter's bundled agent with the staged cadrumo-mcp relay; `dev/runtime_lifecycle/agent_live.py`.
- [ ] `S04` - Remove the desktop direct-start feature and repoint the desktop agent live lane onto the runtime's hosted agent door with the catalog's provider and key names; `native/desktop/src-tauri/src/agent/direct.rs`.
- [ ] `S05` - Drive the one-time hosted tool-access proof run on the staged package for the cadrumo-agent owner to record; `dev/runtime_lifecycle/agent_live.py`.

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

S01 is independent and runs first.
- S02 and S03 can run in parallel once the canonical-environment fix lands in the package. They touch disjoint files.
- S04 follows S03, because it reuses the hosted-door launch S03 proves.
- S05 is last, and it runs with CADRUMO-AGENT-CODE.
- Native builds use a build directory not in use by another session. tui-ee owns `build/windows-x64` and `build/distribution-windows-x64` while its cold build runs.

## Verification

- S01:
  - `just check-style`, `just check-types` and `just check-import-boundaries` pass;
  - the module-reachability, symbol-usage and export-consumption gates stay at zero;
  - `dev/tests/test_dev_cli_justfile_wiring.py` and `dev/tests/test_lane_reachability.py` pass;
  - `dev/audit/tests/test_vulture_whitelist_is_not_stale` passes.
- S02: CTest `bundle.agent` passes on a fresh `Release` bundle. A planted launch failure (a module that does not exist) makes it fail.
- S03: `just verify-agent-live` passes against `stage/<Config>/app`, with no checkout path in its receipt.
- S04:
  - `agent-direct-start` and `direct.rs` are gone;
  - the desktop builds without the feature;
  - `just desktop-agent-live` reaches the agent through the runtime's door.
- S05: CADRUMO-AGENT-CODE records the tool-access proof. Afterwards, a hosted start from the package reaches `agent_ready`.
- Plan close: one integrated review against the ADR.
