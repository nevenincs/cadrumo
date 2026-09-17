---
tags:
  - '#plan'
  - '#filing-chain-reconciliation'
date: '2026-09-17'
tier: L1
related:
  - '[[2026-09-17-filing-chain-reconciliation-adr]]'
modified: '2026-09-17'
body_schema: body-v2
body_hash: 'sha256:9455a4cab52f3b9d328e75d779bd22bbe929fab369f69389c3efa4d636c3c8a2'
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
     Replace filing-chain-reconciliation with a kebab-case feature tag, e.g. #foo-bar.
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

# `filing-chain-reconciliation` plan

Filing chain, AEAT reconciliation and audited overrides, delivered through the CLI and TUI.

## Description

Approved 2026-09-17. Basis: the operator pre-authorised every approval gate for this feature and asked for autonomous delivery.

Deliver the filing chain, AEAT reconciliation and audited manual overrides decided in `2026-09-17-filing-chain-reconciliation-adr`, grounded in `2026-09-17-filing-chain-reconciliation-reference`. Decision coverage: that ADR governs every Step, and no other decision is involved.

Ownership:
- **Backend worker:** S01 to S04 (domain, application and persistence, plus their existing tests and error and event registries).
- **Surfaces worker:** S05 to S07 (CLI, composition seam, TUI, CLI locales, the generated CLI reference and the scenario test).
- **Orchestrator:** integration, scoped checks and commits.
## Steps

- [ ] `S01` - Add chain-entry origin, confirmation, declaration kind and register ref to the filing record with catalogue helpers and forward migration; `src/cadrumo/domain/modelos/filing_record.py`.
- [ ] `S02` - Add the reconciliation service with its register-entry input and five outcomes; `src/cadrumo/application/modelo/filing_chain_reconciliation.py`.
- [ ] `S03` - Split the observation store into official and pending-local layers and replace the displacement guard with audited overrides; `src/cadrumo/adapters/persistence/profile/calculation_observations.py`.
- [ ] `S04` - Rewire file, amend, import and live pull through the chain transitions and the reconciliation service; `src/cadrumo/application/modelo/amendment_actions.py`.
- [ ] `S05` - Expose chain, outcomes, layers and overrides in the CLI and add the Sede port factory seam; `src/cadrumo/entrypoints/cli/_modelo_records_cli.py`.
- [ ] `S06` - Show chain columns and reconciliation and override events in the TUI filing history; `src/cadrumo/entrypoints/tui/declarations/filing_history.py`.
- [ ] `S07` - Add the multi-period CLI-driven reconciliation scenario with a recorded pull port; `src/cadrumo/entrypoints/cli/tests/test_filing_chain_reconciliation_cli.py`.

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

     ## Wave `W01` - ...
     ## Wave `W02` - ...

     The ## Epic intent block is mandatory at L4 and absent at L1, L2,
     L3. The plan title (the level-one # heading at the top of the
     document) is the Epic title; no separate Epic heading is emitted. -->

## Parallelization

- The backend worker first lands the S01 and S02 contract: domain types and the service signature.
- The surfaces worker then starts S05 to S07 against that contract while the backend worker completes S03 and S04. The two write sets are disjoint.
- S07's final run waits for S04.
- Workers run no git. Each worker runs only the test files it creates or edits, sequentially. The orchestrator runs lint, types and the scoped suites once, after handoff.
## Verification

The success criterion is `src/cadrumo/entrypoints/cli/tests/test_filing_chain_reconciliation_cli.py`. It drives only the real CLI (`invoke_cached_cli`, `--json`) against an isolated profile, over three consecutive M130 quarters taken from the support envelope. AEAT pull events come from a recorded in-memory Sede port installed at the composition factory. The scenario:

1. Pull originals for Q1 and Q2. Both outcomes are `APPENDED` and `CONFIRMADA`.
2. Amend Q1 (complementaria). The chain shows `PENDIENTE` amending the confirmed original. Q3 calculate carries the amended Q1 value, and Q3 file is blocked by `LOCAL_FILING_MISSING_EXTERNAL_EVIDENCE`.
3. Re-pull with only the Q1 original. The outcome is `ALREADY_RECORDED`, and the amendment stays `PENDIENTE` (no false confirmation).
4. Amend Q1 again. The first amendment becomes `DESCARTADA`, and the new one amends the confirmed original.
5. Pull a matching Q1 complementaria. The outcome is `CONFIRMED`, the pending layer is cleared, and Q3 file succeeds as `PENDIENTE`. A Q3 pull then returns `CONFIRMED`.
6. Amend Q2, then pull a Q2 complementaria with different content. The outcome is `CONTRADICTED` with the differing casillas, the AEAT entry is in force and the local entry is `DISCREPANTE`.
7. Override a Q2 observation value with `observe-local --reason`. `filing-record view` shows the override audit and both layers, and the dependent gate flags it. `--clear` restores the official layer.

Also required:
- A declarations-screen pilot test shows the chain columns and events.
- The owning suites for the touched modules pass, and lint and types are clean on the touched files.
- The generated CLI reference is regenerated through its generator.