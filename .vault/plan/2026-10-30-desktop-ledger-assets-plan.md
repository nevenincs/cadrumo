---
tags:
  - '#plan'
  - '#desktop-ledger-assets'
date: '2026-10-30'
tier: L1
related:
  - '[[2026-10-23-desktop-ledger-editor-adr]]'
  - '[[2026-10-05-desktop-design-system-adr]]'
  - '[[2026-09-21-assets-core-lifecycle-contract-adr]]'
  - '[[2026-09-23-assets-core-amortization-method-set-adr]]'
  - '[[2026-10-30-desktop-ledger-assets-reference]]'
modified: '2026-10-30'
body_schema: body-v2
body_hash: 'sha256:8271a45d0ef5fa1a6a6805f15a306ff34946d7411ad8cf7a44b230267ea722d9'
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
     Replace desktop-ledger-assets with a kebab-case feature tag, e.g. #foo-bar.
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

# `desktop-ledger-assets` plan

<!-- One-line headline summary plan. -->

## Description

Approved 2026-10-30. Basis: the operator's direct instruction to this session (CADRUMO-AMORTIZATION-UX) to implement the React and thin Rust side of adding, editing and removing assets and inventory items in a new Ledger tab, and to audit how the amortization schedule and timeline are displayed and logged. The operator proposed the tab name Assets, placed before the Setup menu.

The design is `2026-10-30-desktop-ledger-assets-reference`. `2026-10-23-desktop-ledger-editor-adr` governs host admission and write states, and adding operation ids amends it at S05. `2026-10-05-desktop-design-system-adr` governs S01 to S04 and S06. The two assets-core ADRs bound what the views may claim. No business logic enters React or Rust. No new costly decision is involved; the backend contracts come from `2026-10-30-assets-core-plan` S06, S11 and S12.

Inventory edit and remove have no backend operation and no owner; this was raised with the operator on 2026-10-30 and is unanswered. S06 ships only what the registered operations allow unless that changes.

## Steps

- [x] `S01` - Lay the foundation: provisional contract module, words, YearStepper, synthetic fixtures and the RightPanel width prop; `native/desktop/frontend/src/components/ledger/assets/, native/desktop/frontend/src/dev/assetsFixture.ts`.
- [x] `S02` - Build the Assets section shell, element list, detail panel and filing handoff, in stories only; `native/desktop/frontend/src/components/ledger/assets/AssetsSection.tsx, FixedAssetsPane.tsx, AssetList.tsx, AssetDetail.tsx`.
- [ ] `S03` - Build the amortization plan and append-only timeline views, in stories only; `native/desktop/frontend/src/components/ledger/assets/AmortizationPlan.tsx, AssetTimeline.tsx`.
- [ ] `S04` - Build the options-driven forms for element, descriptor, correction, claim and baja, covering every write state; `native/desktop/frontend/src/components/ledger/assets/AssetForm.tsx, DescribeForm.tsx, CorrectForm.tsx, ClaimFlow.tsx, BajaForm.tsx`.
- [ ] `S05` - Conform to the landed S06, S11 and S12 contracts, amend the ledger editor ADR, admit the new ids and delete the provisional module; `native/desktop/frontend/src/components/ledger/assets/, native/desktop/src-tauri/src/shell/ledger/admitted.rs, .vault/adr/`.
- [ ] `S06` - Build the Existencias panel, run valuation preview as a held write, add the assets tab before Setup and retire the Setup panes; `native/desktop/frontend/src/components/ledger/assets/InventoryPanel.tsx, native/desktop/frontend/src/components/ledger/setup/RegistersSection.tsx, ledgerWords.ts, layout.ts`.
- [ ] `S07` - Review the integrated tab in the running app and append findings to the audit; `.vault/audit/`.

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

S01 comes first. S02, S03 and S04 then run in parallel with disjoint files; string keys go to the S01 owner, who holds the strings file and fixtures. S05 waits on the backend contracts and lands with the manifest change in one step coordinated with CADRUMO-AMORTIZATION2. S06 follows S05, because the tab ships only when its operations are real. S07 is last. Other sessions share this worktree, so commits name explicit paths.

## Verification

A person can add an element, set its name and serial, correct it, record and supersede a dotacion, give it a baja, and read its plan and timeline in the running desktop window, through registered operations only. Stories cover every state in the reference, including a decades-spanning ledger. A missing claim never reads as zero or a refusal, and an unknown write pauses writes and is never resent. No method, rate or year list exists in React or Rust. Frontend tests, typecheck, the Rust admission test and the locale gates pass, and the integrated review passes.
