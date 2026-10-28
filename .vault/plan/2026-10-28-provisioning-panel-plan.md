---
tags:
  - '#plan'
  - '#provisioning-panel'
date: '2026-10-28'
tier: L1
related:
  - '[[2026-10-18-dependency-provisioning-unified-setup-adr]]'
  - '[[2026-10-24-rust-component-provisioning-adr]]'
  - '[[2026-10-25-agent-owned-models-adr]]'
  - '[[2026-10-27-sede-browser-adr]]'
modified: '2026-10-28'
body_schema: body-v2
body_hash: 'sha256:f8a0fbddb83c8e132212ba93b44bb5575d2d0a37de4a54bd956bfc65c137379f'
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
     Replace provisioning-panel with a kebab-case feature tag, e.g. #foo-bar.
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

# `provisioning-panel` plan

<!-- One-line headline summary plan. -->

## Description

<!-- First line after approval: `Approved yyyy-mm-dd`, written by the
orchestrator after establishing scoped authorization, including an explicit
advance authorization. Record its basis; ask only when it is absent. Then briefly describe the proposed work.
Reference `{adr}`s, `{research}`, `{reference}`. Supporting documentation
must be read when relevant. State the decision coverage assessment; when no
costly decision is involved and no ADR governs, say so. With several ADRs,
map their scope to Steps at L1 or the relevant containers at higher tiers. -->

Approved 2026-10-28. Basis: the owner's first-hand request of 2026-10-28 in conversation, which gave the rulings recorded in the 2026-10-28 amendment of 2026-10-18-dependency-provisioning-unified-setup-adr and asked for the work to be carried out by agents (Sonnet high for straightforward changes, Opus medium for architecture).

Replace the desktop's single-run setup dialog with one per-element provisioning panel fed by the engine's one state source. Decision coverage: the unified-setup ADR as amended 2026-10-28 governs the panel, Settings, the global signal and blocked features (S03, S04, S02); 2026-10-24-rust-component-provisioning-adr governs engine ownership, the per-item locks and the local AI parts (S01); 2026-10-25-agent-owned-models-adr governs which models appear as local AI sub-elements (S01, S03, S04); 2026-10-27-sede-browser-adr governs the Sede panel (S02). No further decision is needed.

## Steps

- [x] `S01` - Give the desktop setup host one independent run per item, with per-part progress for the local AI program and model, and replace the snapshot's single setup with runs keyed by item in the Rust wire and the TypeScript contract; `native/desktop/src-tauri/src/shell/setup/, native/application/src/provisioning/ where per-part progress needs it, native/desktop/frontend/src/ipc/contract.ts, native/desktop/frontend/src/shell/setup.ts and tests`.
- [x] `S02` - Route a Sede panel refused for a missing browser to the browser's setup verdict, log the refusal locally as a warning, and show the browser's sentence with the button that opens the provisioning panel; `native/desktop/src-tauri/src/shell/sede_view.rs, src/cadrumo/adapters/outbound/aeat/browser/sede_view.py where the verdict is lost, native/desktop/frontend/src/components/browser/ and tests`.
- [x] `S03` - Build the one provisioning panel and the global provisioning store: one row per engine row with its own action, progress and status said once, the local AI as a dropdown holding one local AI component (Ollama program row plus the existing LocalModels list with custom add, per-model download, progress and remove) that the agent settings' Ollama controls also render in place of their own localAiSetup, a close button, used at startup and from every recovery; delete SetupDialog, SetupAdvisory and the hardcoded kind maps; add the rail Settings spinner overlay; `native/desktop/frontend/src/components/setup/, native/desktop/frontend/src/components/settings/LocalModels.tsx, native/desktop/frontend/src/components/AgentColumn.tsx, native/desktop/frontend/src/shell/setup.ts, native/desktop/frontend/src/shell/provisioningRecovery.ts, native/desktop/frontend/src/App.tsx, locale catalogues via dev.locales, stories and scenario tests`.
- [x] `S04` - Reduce Settings to one provisioning section with a status label and a button opening the panel, remove the Local AI button and the browser section, and conform Settings, the panel and the local AI component to their Storybook stories; `native/desktop/frontend/src/components/Settings.tsx, Settings.stories.tsx, native/desktop/frontend/src/components/setup/ stories, native/desktop/frontend/src/components/settings/LocalModels.stories.tsx`.
- [ ] `S05` - Verify on the dev server and scenarios first, then rebuild the desktop from the current tree and confirm startup panel, per-element installs running together, rail spinner, Settings section and the Sede browser-missing offer; `development build targets and the plan ledger, no product files`.

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

<!-- State which Steps, Phases, or Waves can be executed in parallel and
which carry hard ordering. At `L1` and `L2`, parallelism is decided
per-Step or per-Phase. At `L3` and `L4`, Waves are sequenced by
default (one Wave must land before the next can begin); Phases
within a single Wave may be parallelized when they share no hard
interdependency. -->

S01 and S02 run in parallel: S01 owns the desktop setup host, the engine progress events, the setup wire, `ipc/contract.ts` setup types and `shell/setup.ts`; S02 owns the Sede view path and `components/browser/`. S03 starts after S01 lands, since it builds on the per-item wire. S04 follows S03, which owns the panel's element row that S04 reuses. S05 runs last, once no worker or peer build is active in `build/windows-x64`.

Assignments: S01, S02 and S03 Opus medium (architecture and cross-layer); S04 Sonnet high; S05 Opus medium.

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

- A browser setup and a local AI setup run at the same time, each reviewed, cancelled and resumed on its own; Rust tests cover concurrent items and joining one item.
- No React, Rust host or Python surface enumerates items, kinds, sizes or states of its own; the panel renders the snapshot's rows, and an unknown size never shows as zero.
- The local AI shows the program and each listed model as separate sub-elements with separate progress.
- One React component lists and manages provisioning; it opens at startup, from Settings' one section and from every recovery, states each status once and has a close button; closing never stops a run.
- The rail's Settings button shows the spinner overlay while any run is live, driven by the one global store.
- A Sede panel without a browser logs a local warning and offers the browser's setup.
- Frontend lint, type check, unit and scenario tests, the touched Rust and Python tests pass; the dev server is checked before the rebuild, and the rebuilt app is checked from the current tree.
