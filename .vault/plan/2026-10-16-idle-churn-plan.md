---
tags:
  - '#plan'
  - '#idle-churn'
date: '2026-10-16'
tier: L1
related:
  - '[[2026-10-16-idle-churn-adr]]'
modified: '2026-10-16'
body_schema: body-v2
body_hash: 'sha256:488da4e61a2c5487b802ec9b5fdc952e6d9befdff02757c168e63a52e8797f69'
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
     Replace idle-churn with a kebab-case feature tag, e.g. #foo-bar.
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

# `idle-churn` plan

Remove every idle polling loop, so a Cadrumo installation with the desktop open does no work while nothing changes.

## Description

Approved 2026-10-16. The operator asked in this session for the root causes of idle runtime CPU and process churn to be fixed, for every recurring check to use proper signals, and for the Python wait-with-timeout process loops to be migrated.

`2026-10-16-idle-churn-adr` governs every Step. Its evidence is `2026-10-16-idle-churn-audit`. S01 and S02 reduce per-turn cost with no new protocol. S03 adds the cues and the watch flag that S04-S07 consume. S08 and S09 replace the remaining timed waits in the transport and the runtime lifecycle. S10 re-measures the same idle desktop.

Concurrent owners: CADRUMO-FIX1 has uncommitted shared-person-hold hunks in `shell/sign_in/mod.rs`, `agent/mod.rs`, `agent/person.rs` and `shell/language.rs`. CADRUMO-RUNTIME-DEBUG or CADRUMO-BUILD-DEBUG has a `_report_failure` hunk in `session_hold.py`, and RUNTIME-DEBUG has hunks in `session_authority_core.py`. Edits keep those hunks, and commits stage only this plan's hunks. The operator's running desktop (pid 60364) is not restarted. CADRUMO-BUILD-DEBUG rebuilds `stage/Debug` when the operator closes it.

## Steps

- [x] `S01` - Verify a service image once per connection and recheck only the kernel incarnation on later requests; `src/cadrumo_runtime/adapters/service_verification.py`.
- [x] `S02` - Wait for the earliest lease deadline or a custody change instead of the 0.1 s worker expiry loop; `src/cadrumo_runtime/host/worker_service.py`.
- [x] `S03` - Add sign-in, service-lease and attendance cues with coalesced publication and a sign-in watch flag, and publish language cues on operation completion; `src/cadrumo_client/contracts/session_events.py`.
- [ ] `S04` - Drive the agent service from its connection events and stdin lifetime with cached generations; `src/cadrumo_agent_service/main.py`.
- [ ] `S05` - Make the session hold block on one queue and emit unsolicited event lines; `src/cadrumo_runtime/host/session_hold.py`.
- [ ] `S06` - Add the cadrumo-runtime session watch child; `src/cadrumo_runtime/host/session_watch.py`.
- [ ] `S07` - Share one watch-driven sign-in observation across the sign-in view, language host and agent host, and push attendance changes to the window; `native/desktop/src-tauri/src/shell/sign_in/observation.rs`.
- [ ] `S08` - Block idle transport loops on the channel and a wake handle; `src/cadrumo_client/transport/verified_transport.py`.
- [ ] `S09` - Wake runtime lifecycle observation on deadlines, explicit wakes and Windows session notifications; `src/cadrumo_runtime/host/profile_connections.py`.
- [ ] `S10` - Measure the rebuilt desktop at idle and record the result; `.vault/audit/2026-10-16-idle-churn-audit.md`.

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

S01, S02 and S08 are independent of the rest. S04, S05, S06 and S07 depend on S03, and S07 also depends on S05 and S06. S09 follows S08 because both change how the runtime's accept and connection loops wait. One session executes the Steps in order. Nothing is delegated.

## Verification

- Each Step's focused tests drive the real owner. A cue test performs the mutation and observes the cue on the connection. Expiry tests use the injected clock.
- Ruff, the format check, the import linter and the type runner pass on the touched files. For S07, cargo check, clippy and the crate's unit tests pass, along with the frontend type check.
- S10: with the rebuilt desktop open, signed in and idle for at least 60 s, the 30 s process enumeration shows no new Cadrumo child processes. Every long-lived Cadrumo process stays below 1% of one core. A `py-spy record` of the runtime and the worker shows no recurring work.
- The plan closes after an integrated review of the changed behavior against the ADR.
