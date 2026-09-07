---
tags:
  - '#plan'
  - '#tuimodelo'
date: '2026-09-07'
tier: L3
related:
  - '[[2026-09-07-tuimodelo-reference]]'
  - '[[2026-09-07-tuimodelo-form-projection-adr]]'
  - '[[2026-09-07-tuimodelo-filing-lifecycle-adr]]'
  - '[[2026-09-07-tuimodelo-reconcile-verify-adr]]'
  - '[[2026-09-07-tuimodelo-export-destinations-adr]]'
  - '[[2026-09-07-tuimodelo-work-creator-adr]]'
  - '[[2026-09-07-tuimodelo-satellite-families-adr]]'
modified: '2026-09-07'
body_schema: body-v2
body_hash: 'sha256:767b3acf598a6a927fe1aa584e4cd919d4a98637cc423c28d721227df546a609'
---

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the
       related: field above.
     - The related: field carries the AUTHORISING documents
       (ADR, research, reference, prior plan) for every Step in
       this plan. Steps inherit this chain; per-row reference
       footers do not exist.
     - NEVER use [[wiki-links]] or markdown links in the
       document body. -->

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #plan) and one feature tag.
     Replace tuimodelo with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     tier is mandatory for new plans. Allowed: L1, L2, L3, L4.
     L1 = Steps only. L2 = Phases above Steps. L3 = Waves above
     Phases above Steps. L4 = Epic above Waves above Phases above
     Steps; PM association required. Pre-existing plans without this
     field default to L2.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'. The related field
     carries the AUTHORIZING documents (ADR, research, reference, prior
     plan) for every Step in this plan; Steps inherit this chain;
     per-row reference footers do not exist.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->


<!-- HIERARCHY AND TIERS:
     Epic > Wave > Phase > Step. Step is the canonical leaf-row
     noun. Execution Record artifact: <Step Record>.
     Tier is declared in frontmatter as tier: L1/L2/L3/L4
     (mandatory for new plans; pre-existing plans without the
     field default to L2 and the writer adds the field on first
     edit). The tier selects containers:
       L1 = Steps only.
       L2 = Phases above Steps.
       L3 = Waves above Phases above Steps.
       L4 = Epic above Waves above Phases above Steps; MUST declare
            a project-management association in the Epic intent
            block prose.
     Selection is by complexity criteria, not container counting.
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

<!-- NO COMPRESSION:
     N self-similar actions = N rows. Never collapse into "for each
     X, do Y" / "across all callers, do Z" / "in every module,
     replace W". The rule applies at every tier including L1. -->

<!-- VAULTSPEC-CORE VAULT PLAN CLI:
     The `vaultspec-core vault plan` CLI is the canonical surface for
     structural manipulation of this plan document. Writers and
     executors MUST use `vaultspec-core vault plan step add/insert/move/
     remove/check/uncheck/toggle/edit`,
     `vaultspec-core vault plan phase add/move/remove/edit`,
     `vaultspec-core vault plan wave add/move/remove/edit`,
     `vaultspec-core vault plan epic intent`, and
     `vaultspec-core vault plan tier promote/demote` for every
     identifier-affecting change rather than hand-editing the row
     grammar. Hand edits are tolerated by the parser but flagged by
     `vaultspec-core vault plan check`; canonical-identifier preservation is
     guaranteed only when the CLI performs the mutation. Run
     `vaultspec-core vault plan --help` for the full subcommand
     surface. -->

# `tuimodelo` plan

<!-- One-line headline summary plan. -->

## Description

<!-- Briefly describe the proposed work. Reference `{adr}`s,
`{research}`, `{reference}`. Supporting documentation must be read prior to
writing the plan document. A plan may execute one ADR or a cluster; when
several feed it, state here which Wave or Phase each ADR governs. -->

## Steps

## Wave `W01` - governance hygiene and admission gate

Clear the governance debt that blocks every later wave. A dead campaign still holds seven rows of the tui-architecture plan open against a gate that can never close, two tui-interface rows describe a retired mechanism, and the action denominator cannot yet prove admission because its drift check never observes a disposition or an interface capability. Nothing downstream can be scheduled honestly until scope is annotated, holds are adjudicated and the gate can fail in both directions.

<!-- The plan's tier (declared in frontmatter as `tier: L1`, `L2`, `L3`, or
`L4`) determines the structure under this section:

- `L1`: a flat list of Step rows (no Phase, Wave, or Epic).
- `L2`: one or more `### Phase` blocks each containing Step rows.
- `L3`: one or more `## Wave` blocks each containing Phase blocks.
- `L4`: a `## Epic intent` block, followed by Wave blocks. -->

<!-- Replace this scaffold with the tier-appropriate structure for your plan.
Format examples for each block type are embedded below as commented
templates. -->

<!-- IMPORTANT: This document must be updated between execution runs to
     track progress. -->

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

     ## Wave `W01` - ...
     ## Wave `W02` - ...

     The ## Epic intent block is mandatory at L4 and absent at L1, L2,
     L3. The plan title (the level-one # heading at the top of the
     document) is the Epic title; no separate Epic heading is emitted. -->

## Wave `W02` - adapter to backend migration

Make both adapters pure consumers. The session-authorization matrix keys on operator-typed verb strings, so no full-screen surface can be authorized until it moves; that leads. The modelo lane then relocates the policy it holds - history, casilla visibility, effective lifecycle state, override admissibility, the detail-row grammar with its intracommunity legal rule - and the frontend sheds the duplicate persistence wiring it already carries.

## Wave `W03` - declared form projection

Give every generated surface an ordering, a grouping and an honest coverage number. Fix the three value-handling defects that would otherwise ship an editor accepting arbitrary text into identity fields, then define the declaration, build the generator over official sources, and gate coverage and cross-revision stability.

## Wave `W04` - the reachability join

Turn built-but-unreachable capability into reachable capability. One missing navigation mechanism keeps history, the editor, verification and every action surface unreachable at once; supervision keeps the mutations outside the operation registry. This wave is where the campaign's existing investment starts returning.

## Wave `W05` - editing and calculation inputs

Deliver the casilla editor over the admission seam that already exists, including the repeated-row surface that detail-row modelos have never had, and the observation-entry surface that four withholding modelos depend on.

## Wave `W06` - reconcile and verify

Make comparison attributable and verification complete. Name which comparison ran, render the whole finding rather than a fragment, and disclose withheld advisories instead of omitting them.

## Wave `W07` - export, import and destinations

Give artefact movement a shared contract in both directions, wire the exporter that already exists, and bring import under the supervisor with the preview and per-item reporting the ledger lane already proved.

## Wave `W08` - declaration creation

Discharge the deferred creation mandate on corrected terms, governing the period-first affordance the calendar already offers rather than adding a second one.

## Wave `W09` - satellite family dispositions

Deliver, fold, or explicitly close every remaining denominator family, so that no capability is dropped by silence.

## Wave `W10` - acceptance and independent review

Prove the campaign against the matrix the governing decision requires, publish final coverage, and submit the workbench to independent review.

## Parallelization

<!-- State which Steps, Phases, or Waves can be executed in parallel and
which carry hard ordering. At `L1` and `L2`, parallelism is decided
per-Step or per-Phase. At `L3` and `L4`, Waves are sequenced by
default (one Wave must land before the next can begin); Phases
within a single Wave may be parallelized when they share no hard
interdependency. -->

## Verification

<!-- State the mission success criteria for this plan. Each criterion
should be a verifiable check (test passes, surface conforms,
reviewer signs off) rather than a free-form assertion.

The plan is complete when every Step in the plan is closed
(`- [x]`). At `L4`, the Epic-completion check additionally requires
the declared project-management association to report the Epic
complete.

For tier-specific verification cadence, see the authorizing
documents linked in the `related:` frontmatter. -->
