---
tags:
  - '#plan'
  - '#local-ai-on-demand-server'
date: '2026-11-11'
tier: L1
related:
  - '[[2026-11-07-local-inference-engine-adr]]'
  - '[[2026-10-04-runtime-manager-architecture-adr]]'
  - '[[2026-10-24-rust-component-provisioning-adr]]'
modified: '2026-11-11'
body_schema: body-v2
body_hash: 'sha256:eee3cb34c2a1925b203e35073f7e0683e733d06bb7551b15da4fd39a7f9df990'
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
     Replace local-ai-on-demand-server with a kebab-case feature tag, e.g. #foo-bar.
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

# `local-ai-on-demand-server` plan

Run the local AI server only while a document is being read, never at launch, status or setup.

## Description

Approved 2026-11-11. Basis: CADRUMO-COORDINATOR's rulings of 2026-11-11 under delegated design authority. They approve the on-demand server, the manager IPC verb as its only channel with agent-service-only admission, a dormant start, a 5-minute idle stop, no demand from status or setup, and the E13 re-scope. They accepted the 2026-11-11 amendment of `2026-11-07-local-inference-engine-adr`, which this plan implements, and its reconciliations of `2026-10-04-runtime-manager-architecture-adr` and `2026-10-24-rust-component-provisioning-adr`. Build 16 is the target.

Build 15 started llama-server at GUI launch: an idle router holding no model, 38 MB, respawned about one second after each stop by process ID. The manager started it with its supervision. S01 to S03 make the server dormant and start it only on an admitted demand. S04 and S05 keep the status and setup surfaces from needing a running server. S06 makes the agent service the demander. S07 carries the window fixtures.

The demand is a lease. Each demand keeps the server for 5 minutes, and the agent service renews it while a local-lane read runs, so an idle stop never ends a read in progress. Transport facts: the agent service is the digest-verified `cadrumo-agent-service` image, a child of the desktop (`native/desktop/src-tauri/src/agent/mod.rs`). The manager pipe admits only manager and desktop images (`native/manager/src/ipc/windows.rs` `inspect_peer`). `SuccessorReady` shows the pattern for admitting a caller per request.

## Steps

- [x] `S01` - Add the dormant state, demand lease, 5-minute idle stop and restart-only-while-demanded rule to the server supervisor, with tests that a PID stop of a dormant or idle-stopped server never restarts it; `native/application/src/provisioning/local_ai/supervision.rs`.
- [x] `S02` - Run the manager's local AI host dormant at start, carry a demand command to its supervision thread, treat dormant as idle in its loop, and update the host tests; `native/manager/src/supervision/local_ai.rs`.
- [x] `S03` - Add the closed demand_local_ai manager request and its outcomes, admit it only for the digest-verified agent-service image whose parent is the admitted desktop, and serve it from both the installed and the desktop-hosted manager; `native/manager/src/ipc.rs`.
- [x] `S04` - Serve dormant as its own local AI state in the quick check instead of program_not_running, with backend words in every locale; `native/application/src/provisioning/local_ai/models.rs`.
- [x] `S05` - Make setup verify the program and models from files without leaving a server running, serve the local engine as ready only when a model file it can run exists (build 15 showed 'Listo' on the lane and the setup dialog with zero models), and re-scope program_not_running and server_wait_expired to a failed demanded start; `native/application/src/provisioning/engine.rs`.
- [x] `S06` - Add the agent service's manager-pipe client, demand the server before a local-lane run and renew it while the run lasts, and refuse with a served reason when the manager cannot be reached; make a local engine's provider lane read as its served local AI setup row, so no runnable model file reads not set up and a dormant server reads ready (COORD 2026-11-11); `src/cadrumo_agent_service/host`.
- [ ] `S07` - Relay a manager-supervised local engine lane in the agent service's catalog from the manager's served local AI facts, not the agent's probe: installed from the model files, a dormant server selectable and ready, not running only after a failed demand, unknown only when the served row is unavailable; service tests for asleep, running, failed demand and row unavailable; no cadrumo-agent change, the window only renders (COORD 2026-11-11). Update the desktop setup fixture and scenarios for the dormant state and hand the native build and Playwright to DESKTOP; `native/desktop/frontend/src/dev/setupFixture.ts`.

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

S01 comes first. S02 and S04 depend on it and can proceed in parallel. S03 depends on S02, and S06 depends on S03. S05 depends on S04. S07 comes last. One worktree (`fix/local-ai-on-demand-server`), with one commit per Step. Rust compiles, cargo tests, the native build and Playwright run in root by DESKTOP, so the Rust Steps are handed to DESKTOP to verify as they close.

## Verification

- Supervisor tests: no server runs until a demand. A demanded server runs and restarts after a crash. The server stops 5 minutes after the last demand. A PID stop of a dormant or idle-stopped server never restarts it.
- Manager tests: the host starts dormant. A demand answers ready once the server answers. The new request is refused for every image except the agent service.
- A packaged build 16 run under real WebDriver: no llama-server process at GUI launch, at a status check or at setup. One extraction starts it, and it is gone 5 minutes after the extraction.
- The quick status reads dormant with backend words in every locale, never `program_not_running`.
- Python: agent-service tests for the demand client and the refusal when the manager cannot be reached.
- The landing ratchet adds 0. The locale tests pass in full.
