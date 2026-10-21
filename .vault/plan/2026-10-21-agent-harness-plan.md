---
tags:
  - '#plan'
  - '#agent-harness'
date: '2026-10-21'
tier: L1
related:
  - '[[2026-07-02-agent-harness-refoundation-adr]]'
modified: '2026-10-21'
body_schema: body-v2
body_hash: 'sha256:5d08f1f1e6ac6c4d23ad8a21dc04db9cb169d32d5647f648132589f209bce33e'
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
     Replace agent-harness with a kebab-case feature tag, e.g. #foo-bar.
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

# `agent-harness` plan

Remove every piece of the agent harness from Cadrumo so that only the deterministic MCP service, the agent-key grant scope and the agent service host remain, matching the cadrumo-agent implementation.

## Description

Approved 2026-10-21. Basis: in session TUI-REFACTOR the user directed that tui carry none of the harness (skills, rules and the rest), that cadrumo-agent is its implementation, and that this work proceed without further approval gates ("go").

This is drift repair, not a new decision. cadrumo-agent's accepted `2026-10-15-agent-harness-adr` (cadrumo-agent vault) already rules that cadrumo-agent owns all authored agent content, its metadata, accessors, serving, provisioning and live persona evaluation, and that Cadrumo keeps only its tools, programs, MCP server and declarations. The 2026-10-21 boundary amendments to `2026-07-02-agent-harness-refoundation-adr` and the related Cadrumo ADRs bring this vault into line with that ruling; this plan implements them. No new ADR is involved.

Cadrumo keeps: the deterministic MCP service (`cadrumo-mcp`, package renamed to `src/cadrumo_mcp` in S05), its operation projection, discovery, search and operation-derived guidance, authority and corpus queries, runtime admission and cleanup, progress and diagnostics; the agent-key grant scope; `src/cadrumo_agent_service` as the host that launches the bundled cadrumo-agent and declares the MCP tool server through `CADRUMO_AGENT_TOOL_SERVER_<NAME>`; and deterministic MCP conformance in `dev/mcp_eval`. Cadrumo removes: `src/cadrumo_harness/_data/agent/**`, `_resources.py`, `resources.py`, `_skill_metadata.py`, `workspace.py`, `mcp/operating_layer.py` with `harness_load` and the `cadrumo://skill` and `cadrumo://rule` resources, the workspace materialisation flag, `dev/harness_data`, and the live persona parts of `dev/agent_eval`. The Claude Code plugin packaging was already removed in `e4188cc067`. No compatibility facade or duplicate definition remains.

The main worktree's uncommitted 2026-10-15 refactor came from a cadrumo-agent session working against the stale 2026-10-08 main base. It is reference material for intent only. Its base predates eleven MCP modules and `src/cadrumo_agent_service`, so it is never applied.

Open items carried from the amended ADRs, settled in implementation as follows. The command-operation reference generator leaves Cadrumo in S03; cadrumo-agent derives operation knowledge from MCP operation discovery. `applies_when` validation leaves Cadrumo in S03; cadrumo-agent's validator already takes a caller-supplied profile model. Porting Cadrumo-only content changes is S01. Provider policy in `src/cadrumo_agent_service` is out of scope here and stays with `2026-10-14-agent-service-boundary-plan`.

## Steps

- [x] `S01` - Port Cadrumo-only skill and rule changes made after the fork into cadrumo-agent and report files held by concurrent cadrumo-agent edits; `Y:/code/cadrumo-agent-worktrees/main/src/cadrumo_agent/harness/_data/agent`.
- [x] `S02` - Remove skill and rule serving from the MCP surface: operating layer, harness_load, cadrumo skill and rule resources, workspace flag and skill-loading tool descriptions; `src/cadrumo_harness/mcp`.
- [x] `S03` - Delete harness content and accessors with their tests, the command-operation reference generator and the wheel data include; `src/cadrumo_harness/_data, src/cadrumo_harness/resources.py, src/cadrumo_harness/workspace.py, dev/harness_data, pyproject.toml`.
- [x] `S04` - Reduce agent evaluation to deterministic MCP conformance in dev/mcp_eval, removing the live persona lane, scoring, flywheel, persona scenarios and eval-agent recipes; `dev/agent_eval, justfile`.
- [ ] `S05` - Rename the package cadrumo_harness to cadrumo_mcp across code, packaging, import contracts, tooling and documentation; `src/cadrumo_harness, pyproject.toml, .importlinter, justfile, dev, docs`.
- [ ] `S06` - Add a protective gate that rejects authored agent content and skill or rule serving in Cadrumo, proven against an isolated defect fixture; `dev/quality/tests`.
- [ ] `S07` - Run import, style, format and type gates and the affected test suites, fixing every failure; `src, dev`.
- [ ] `S08` - Save the main worktree's stale refactor to a side branch and put one squash commit of tui onto local main without pushing; `Y:/code/cadrumo-worktrees/main`.

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

S01 runs in the cadrumo-agent repository and may run in parallel with S02 to S04. It must read the Cadrumo content before S03 deletes it, so it reads from commit `e4188cc067` instead of the working tree. S01 touches only cadrumo-agent files that no concurrent session has uncommitted edits in, and reports the rest. S02 to S07 touch the same package and run strictly in order under one executor. S08 runs last.

## Verification

- `git ls-files src dev` contains no path under `_data/agent`, no `SKILL.md`, and none of `resources.py`, `_skill_metadata.py`, `workspace.py` or `operating_layer.py` in the MCP package. `git grep` over `src` and `dev` finds no `harness_load`, `cadrumo://skill`, `cadrumo://rule` or `cadrumo_harness`, apart from the protective gate's own fixture strings.
- The S06 gate passes on the tree and fails on an isolated fixture that reintroduces a skill document and a skill-serving resource.
- `uv run --no-sync lint-imports --config .importlinter --no-cache`, `just check-style`, `just check-format` and `just check-types` exit 0.
- The `src/cadrumo_mcp`, `src/cadrumo_agent_service`, `dev/mcp_eval`, `dev/runtime_lifecycle` and `dev/packaging` test suites pass, and `cadrumo-mcp` still starts through its console script.
- After S08, local `main` is exactly one commit ahead of `origin/main`, and its tree equals tui's HEAD tree. The main worktree's 2026-10-15 refactor is preserved on its side branch.
- A final integrated review passes.
