---
tags:
  - '#plan'
  - '#clitui-ledger'
date: '2026-09-04'
tier: L3
related:
  - '[[2026-09-04-clitui-ledger-adr]]'
  - '[[2026-09-04-clitui-ledger-research]]'
  - '[[2026-09-04-clitui-ledger-reference]]'
modified: '2026-09-04'
body_schema: body-v2
body_hash: 'sha256:48006f3eb2b0baeffcbf17a68582714a252be8f2c7b15a16f3d73b60a9c36775'
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
     Replace clitui-ledger with a kebab-case feature tag, e.g. #foo-bar.
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

# `clitui-ledger` plan

<!-- One-line headline summary plan. -->

## Description

<!-- Briefly describe the proposed work. Reference `{adr}`s,
`{research}`, `{reference}`. Supporting documentation must be read prior to
writing the plan document. A plan may execute one ADR or a cluster; when
several feed it, state here which Wave or Phase each ADR governs. -->

## Steps

## Wave `W01` - freeze the capability denominator and campaign ownership

Close G0 by freezing the executable capability ledger, assigning semantic homes, and recording sole plan ownership plus the Ledger TUI implementation hold before authority migration begins.

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

### Phase `W01.P01` - define the authoritative capability ledger

Create the stable generated matrix contract, validation, and reference publication used throughout every gate.


### Phase `W01.P02` - freeze the union denominator and ownership

Enumerate commands, backend-only operations, missing products, registry consumers, artifacts, and installed surfaces with explicit applicability and semantic ownership.


### Phase `W01.P03` - record sole plan ownership and the TUI hold

Reconcile overlapping Ledger work without changing production TUI code and make the hold visible in campaign state.


### Phase `W01.P04` - adjudicate and close G0

Review every denominator row and require evidence or explicit UNPROVEN state before authority work starts.


## Wave `W02` - recover backend semantic authority

Close G1 cohort by cohort: implement each typed backend owner, immediately cut affected CLI handlers over to delegation, and retain detector tests that forbid adapter reimplementation.

### Phase `W02.P05` - backport and delegate query and composite-read policy

Implement typed read authorities, cut each affected query and read handler over immediately, then prove the cohort before proceeding.


### Phase `W02.P06` - backport and delegate core mutation policy

Implement manual creation, allocation, classification, and rule-preview authorities, cut each affected handler over immediately, then prove the cohort.


### Phase `W02.P07` - backport and delegate provider and review workflows

Implement import, Drive, evidence-review, consent, and model-routing authorities, cut each affected handler over immediately, then prove the cohort.


### Phase `W02.P08` - backport and delegate invoice and adjacent-register workflows

Implement invoice, counterparty, ratio, prorrata, and bienes authorities, cut each affected handler over immediately, then prove the cohort.


### Phase `W02.P09` - prove the clean authority boundary

Publish canonical outcomes, run structural and behavioral detectors, and close G1 only after every handler delegates and every AUTHORITY finding is closed.


## Wave `W03` - complete and prove the backend product

Close G2 by implementing every missing Ledger operation, artifact, provenance, registry route, and production-behavior proof after every G1 authority cutover is complete.

### Phase `W03.P10` - complete mutation and provenance semantics

Add batch change sets, immutable notes, atomic evidence replacement and download, exact field history, and complete currency lineage.


### Phase `W03.P11` - deliver interchange review and recovery products

Implement distinct flat interchange, review exchange, optional Google transport, and secure recovery archive contracts.


### Phase `W03.P12` - complete reviewable model-assisted classification

Route extraction and classification through the canonical model registry with consent, schema, evidence, suggestion, and reviewer provenance.


### Phase `W03.P13` - close registry calculation and filing routes

Prove all seven Ledger binding families, block every unrouted nonzero observation, and carry full registry and FX provenance into filing evidence.


### Phase `W03.P14` - prove production behavior and close G2

Exercise real repositories, faults, concurrency, artifacts, restore equality, and nonzero calculation compositions before declaring backend completeness.


## Wave `W04` - complete CLI product parity

Close G3 by enrolling capabilities created during G2, removing residual transport and projection defects, and proving complete command and artifact parity without repeating G1 authority cutovers.

### Phase `W04.P15` - enroll G2 core capabilities in the CLI

Add command and payload exposure for batch edits, notes, evidence lifecycle, provenance, and normalization without relocating business policy back into handlers.


### Phase `W04.P16` - close residual CLI provider and projection defects

Expose model, registry, provider, and calculation outcomes created by G2 and remove remaining transport-only parity defects.


### Phase `W04.P17` - complete CLI import export and recovery contracts

Expose every G2 artifact product with explicit destinations, dry runs, stable envelopes, and independent readability checks.


### Phase `W04.P18` - prove command parity and close G3

Require every CLI-applicable matrix row to pass success, refusal, artifact, locale, redaction, exit-code, and delegation detectors.


## Wave `W05` - install and prove TUI parity

Close G4 by lifting the hold, reusing the recensused Ledger components over canonical application doors, installing all applicable workflows, and proving cross-surface parity and reachability.

### Phase `W05.P19` - lift the hold and re-census reusable TUI components

Confirm G3 closure, adjudicate existing Ledger components against current backend contracts, and only then authorize production TUI edits.


### Phase `W05.P20` - build complete Ledger TUI workflows

Implement read, review, mutation, evidence, import, classification, and artifact workflows over the same typed backend use cases.


### Phase `W05.P21` - install navigation and operation feedback

Make every applicable workflow reachable from the installed session with selection handoff, confirmation, progress, refusal, and result presentation.


### Phase `W05.P22` - prove cross-surface parity and close G4

Run installed TUI, backend, CLI, registry, artifact, and accessibility gates and regenerate the final authoritative matrix.


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
