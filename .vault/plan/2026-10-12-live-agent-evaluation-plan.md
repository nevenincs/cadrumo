---
tags:
  - '#plan'
  - '#live-agent-evaluation'
date: '2026-10-12'
tier: L1
related:
  - '[[2026-10-12-live-agent-evaluation-adr]]'
  - '[[2026-10-12-mcp-parity-agent-inside-the-signed-in-profile-adr]]'
  - '[[2026-07-02-agent-harness-refoundation-adr]]'
modified: '2026-10-12'
body_schema: body-v2
body_hash: 'sha256:c4f661a5b9d114421a374190de3939e82199d400db56db5969c0c3d3c32fa082'
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
     Replace live-agent-evaluation with a kebab-case feature tag, e.g. #foo-bar.
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

# `live-agent-evaluation` plan

Carry the 2026-10-12 live agent test into the project as a reproducible, opt-in lane that runs a haiku agent over MCP against a verified copy of the built package.

## Description

Approved 2026-10-12. Basis: the owner's first-hand "lgtm" on `2026-10-12-live-agent-evaluation-adr`, which also accepts its defaults (model `claude-haiku-5-5`, three runs with at least two reaching the end state), and the owner's standing instruction that agent work be finished and verified live.

This plan builds `dev/agent_eval/live/` and its two recipes as the governing ADR's Implementation section lays out. Decision coverage: `2026-10-12-live-agent-evaluation-adr` governs every Step (package copy, isolated root, scenarios, drivers, capture, oracle, access scenarios, recipes, floor). `2026-10-12-mcp-parity-agent-inside-the-signed-in-profile-adr` governs the access rules the lane holds from its own side in S03, S05, S06 and S08: the agent never authenticates, never holds a secret, and is refused without a live sign-in or a valid key. `2026-07-02-agent-harness-refoundation-adr` R7 is the substrate the lane drives (`LiveTrajectory`, `score_live_trajectory`). No new costly decision is involved; the evidence is `2026-10-12-live-agent-evaluation-reference`.

Scope bounds: the lane never edits `src/cadrumo_harness/mcp` or runtime code, which belong to the mcp-parity P10 work; it does not depend on the session, installation, authenticate or authorization tools that P10 removes. Person-side acts go through the packaged command line. A package built before P10 lands is expected to fail the no-secret-offered invariant. The live run (S11) waits for P10 and a rebuild, and needs an interactive logon whose credential store works; on an SSH logon the lane reports unavailable.

## Steps

- [x] `S01` - Correct the dev/agent_eval docstring to state what the package imports from the product; `dev/agent_eval/__init__.py`.
- [x] `S02` - Verify the staged bundle package against its manifest, copy it to the development build root, verify and re-verify the copy, and compare its first-party modules with the checkout, refusing a stale package unless asked, with positive controls for a changed byte and a stale module; `dev/agent_eval/live/package_copy.py`.
- [x] `S03` - Host the copied package on a fresh isolated storage root, running the installation record, profile creation, sign-in and teardown as package code through the copy's interpreter and command line, with the runtime launched unsupervised with the manager's arguments inside a kill-on-close scope and an allow-listed environment, and classify an unusable credential store as unavailable; `dev/agent_eval/live/isolated_host.py`.
- [x] `S04` - Declare the live scenario files, Modelo 130 on the DR 130 worked example first and then Modelo 303 for the same quarter, with their loader and required subsequences; `dev/agent_eval/live/scenarios`.
- [x] `S05` - Drive the agent through the Anthropic API with an MCP client loop or the authenticated claude CLI fallback, always claude-haiku-5-5, both producing one LiveTrajectory, with turn, token and spend limits; `dev/agent_eval/live/drivers.py`.
- [ ] `S06` - Scrub the stream before anything is written and capture the scrubbed trajectory, receipt and score to .logs/agent-eval/ behind a fail-closed residual scan, with a positive control on a planted secret; `dev/agent_eval/live/capture.py`.
- [ ] `S07` - Read the oracle through the packaged command line JSON envelopes and the product export parser under the copy's authority, and fail on any disagreement, with a positive control on a planted disagreement; `dev/agent_eval/live/oracle.py`.
- [ ] `S08` - Drive the access scenarios from the person's side through the packaged command line: key issue, use in scope, refusal out of scope, revocation mid-run, locked, signed out and expired, each requiring the agent to send the person back to Cadrumo; `dev/agent_eval/live/access.py`.
- [ ] `S09` - Add the opt-in recipes eval-agent-floor and eval-agent-live with a receipt, the three-run pass rule and distinct outcome classes and exit codes, kept out of every default lane; `justfile`.
- [ ] `S10` - Run the scripted floor on this host and prove that a refused credential store is classified unavailable, never a pass; `dev/agent_eval/live/floor.py`.
- [ ] `S11` - Run the live lane, three runs per scenario, on the operator's interactive desktop logon after the mcp-parity P10 surface lands and the bundle is rebuilt, and record the receipt; `.logs/agent-eval`.

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

Sequential. S02 and S03 precede every Step that runs the package. S04 to S08 can be written in any order once S03 exists, but share the run orchestration and land one at a time. S09 and S10 follow S08. S11 follows P10 of the mcp-parity plan and a bundle rebuild, on the operator's interactive logon.

## Verification

- `dev/agent_eval/tests` passes, including the positive controls: the scrubber fails on a planted secret, the copy check fails on a changed byte and on a stale module, the oracle fails on a planted disagreement, and the verdict rules classify an unusable credential store as unavailable.
- Ruff, ruff format and ty pass on touched files, and `just check-import-boundaries` passes.
- `just eval-agent-floor` and `just eval-agent-live` are declared only in the justfile, are reached by no default lane, and on this SSH host exit with the unavailable class and its reason.
- S11 closes only on a receipt from the operator's interactive logon showing three runs, every hard invariant held and at least two runs reaching the end state with the oracle in agreement.
