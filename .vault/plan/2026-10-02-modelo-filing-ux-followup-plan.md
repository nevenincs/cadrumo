---
tags:
  - '#plan'
  - '#modelo-filing-ux-followup'
date: '2026-10-02'
tier: L1
related:
  - '[[2026-09-30-modelo-editor-workbench-adr]]'
  - '[[2026-09-30-modelo-editor-workbench-operator-layer-adr]]'
  - '[[2026-06-05-calendar-filing-semantics-adr]]'
  - '[[2026-09-07-tuimodelo-filing-lifecycle-adr]]'
modified: '2026-10-02'
body_schema: body-v2
body_hash: 'sha256:db802fc0bf0b290eeb882b3fce239971a1370a4fa47f52319263e985037a15af'
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
     Replace modelo-filing-ux-followup with a kebab-case feature tag, e.g. #foo-bar.
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

# `modelo-filing-ux-followup` plan

<!-- One-line headline summary plan. -->

## Description

Approved 2026-10-02

The operator explicitly instructed this lane to read its reviewed UX4 handoff as its own production mandate and continuity prompt and continue. This authorizes integration, verification and required Step commits for the bounded corrections below. The original modelo-editor-workbench plan remains historically closed at 64/64.

S01 integrates the twelve-path declaration patch, SHA-256 5b7dcb6657f620f7c284de71ab788a14abe48552d253d277918ce78643fab882: truthful typed not-calculated words, separate external AEAT completion, persistent admitted shortcuts, usable outer scrolling and period-selection explanation. S02 integrates only 21 proper Modelo labels, five existing copy leaves and one Hungarian date-punctuation leaf from separately reviewed manifests. S03 removes unavailable field-edit/source guidance on record-only pages using generic typed capabilities. S04 establishes changed-input installed/runtime consumer evidence, actual calendar semantics and independent source/visual review.

Accepted decisions cover these routine changes without a new costly commitment. The workbench decision governs S01-S03 layout, typed capabilities and catalogue wording. The operator-layer decision governs unchanged admission and S04's bounded actual Modelo100 persistence/export assessment. Calendar-filing-semantics and tuimodelo filing-lifecycle govern S01/S04 external evidence, local draft identity, correction urgency and separate amounts. Their evidence is inherited through related references. Registry schemas, authority generation, live AEAT writes, release publication, service adoption, push and PR are outside scope. Native Hungarian human review remains required before release.

Principal review subsequently admitted S05's complete persistent header identity and two existing Catalan proper-name leaves. The actual admitted Modelo100 walk exposed a retained-answer calculation refusal: S06 enriches the existing typed refusal through a private ephemeral projection, connects its named source to Issues and the admitted box/source route, and suppresses obsolete saved-empty qualifiers beside concrete staged values. Workbench D3/D5/D6 and operator-layer typed-precondition coverage apply without a new costly decision. The saved source remains unchanged; an honest explained refusal may close the UX correction without successful persistence or export proof. S04 establishes scoped applicability and composed independent source/visual review.

The final review also found a reachable direct Export path that could ignore pending edits and use an older verified saved result. S07 closes that existing-contract gap and hardens the final export/record callbacks: active prerequisite leads to Issues; otherwise pending True, False, zero or clear leads to Review/Apply with the draft retained. No new output, authority or verification contract is introduced.

## Steps

- [x] `S01` - Integrate reviewed declaration guidance, results and external-filing grouping; `src/cadrumo/application/modelo/declarations_list.py, src/cadrumo/entrypoints/tui/declarations, four common.yml catalogues, dev/locales/fstring_registry.py and owning finite-caption discovery test`.
- [x] `S02` - Apply validated existing Modelo names, declaration copy and period-selection instructions; `four common.yml catalogues, docs/how-to/fill-in-and-file-in-the-workbench.md and its three localized PO paragraphs`.
- [x] `S03` - Align record-only page key guidance with actual admitted field actions; `src/cadrumo/entrypoints/tui/modelo/workbench/{screen,casilla_list}.py, owning help/footer/installed records tests, and the repeating-record paragraph in the workbench guide and its ES/CA/HU PO catalogues`.
- [ ] `S05` - Preserve complete declaration identity and deadline context in the persistent header; `workbench header.py/screen.py, owning header and real formula-value consumer tests, plus existing CA Modelo header name leaves`.
- [ ] `S06` - Explain typed calculation prerequisites after a refused Apply and preserve truthful staged-value qualifiers; `application/modelo edit executor and ephemeral refusal projection, operation composition and installed lifecycle/workbench doors, workbench screen/issues/session/page_items/casilla_list, focused owning tests, four common.yml prerequisite-message leaves and canonical import load-target metadata`.
- [ ] `S07` - Prevent pending edits from exporting or recording an older saved result; `workbench screen.py shared output guard and focused pending True/False/zero/clear boundary tests with actual Review/Issues key evidence`.
- [ ] `S04` - Verify integrated installed filing UX and record the final cohesive review; `owning harness tests and modelo-filing-ux-followup audit`.

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

One implementation owner controls all repository/vault changes, commits, shared installed checks and native captures. S01, S02 and S03 integrate sequentially; S04 reviews their stable combined behavior. Scratch-only proposals and principal filer visual review may prepare in parallel. Bounded translation delegation uses Luna Max; other delegated work uses Sol High/XHigh under explicit operator instructions. Those lanes do not edit repository paths. Preserve unrelated edits and serialize stateful checks/capture.

## Verification

Verify exact patch identity/applyability and all affected file/interpreting dependencies before reusing prior evidence. Run configured format, lint, type checks and owning tests with explicit unit/integration marker selection. Scoped catalogue checks prove four-locale parity, meaningful nonempty translations, exact placeholders, character and terminal-cell limits and minimal key deltas through the canonical locale CLI. Owning import and installed/catalogue consumers must exercise changed inputs.

Acceptance preserves completed original obligations from typed external AEAT evidence, separately retained local drafts and unknown results, correction urgency and no borrowed external amount. Real arrows, Home/End, fold/unfold and focus return reveal the complete selected row via outer scrolling without inner/horizontal overflow at 80/120 columns, four locales and both themes. Fresh changed-surface PNG/text identifies exact keys, timestamps and stable source/authority hashes for independent principal review. Assess admitted Modelo100 answer, persistence, reload and export only through existing hermetic encrypted synthetic supported paths; do not infer them from question PNGs.

Reuse unchanged broad workbench, authority and documentation proof only after recording applicability. Preserve baseline locale/static failures separately from introduced regressions. Completion requires each Step verified and committed with durable ledger checkpoints and one passing final cohesive audit. Agent translation validation does not fulfill native Hungarian release review.
