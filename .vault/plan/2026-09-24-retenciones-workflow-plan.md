---
tags:
  - '#plan'
  - '#retenciones-workflow'
date: '2026-09-24'
tier: L1
related:
  - '[[2026-09-21-retenciones-workflow-observation-payment-contract-adr]]'
  - '[[2026-09-23-retenciones-workflow-evidence-capture-scope-adr]]'
modified: '2026-09-24'
body_schema: body-v2
body_hash: 'sha256:01f07da8eb21cdd1b42b492594972721c60bd0b34c0c6124bf8426894330704d'
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
     Replace retenciones-workflow with a kebab-case feature tag, e.g. #foo-bar.
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

# `retenciones-workflow` plan

Carry Modelo 193 pending-payment and settled-prior-accrual rows from capital withholding into the 2025 export through the one aggregation mechanism.

## Description

Approved 2026-09-24. Basis: the operator's standing authorisation to make changes in this lane, and the coordinator's recorded ordering of the retenciones targets (payroll capture, then capital capture, then the Modelo 193 export); payroll and capital capture have landed.

The phase materialiser in `src/cadrumo/application/aggregation/m193_phase_materialization.py` produces pending and settled-prior-accrual rows but nothing consumes them: the 193 perceptor rows read only the manual 193 window (`withholding_source.py`), captured capital allocations land only in the Modelo 123 quarterly window, and the declarant totals copy Modelo 123 casillas instead of summing the type-2 rows. The 2025 design (HAC/1430/2025, bundled record design pp. 5-7 and 24-26) counts type-2 records, sums them for the declarant totals, and carries the PENDIENTE flag at position 117 and the accrual year at 118-121.

Decision coverage: the observation-payment-contract ADR settles the phase model (keys A, B and D; pending in the accrual year, settled in the payment year) and the evidence-capture-scope ADR settles that the export is wired through the canonical aggregation mechanism with no second summation path. No new decision is needed. Scope stays within those ADRs: pending rows remain limited to 2025 accruals, and extending them to later accrual years needs an ADR amendment first.

S01 and S02 are code; S03 is registry authoring and ships through the coordinator's republish queue; S04 proves the whole path; S05 keeps the filing-export block in place until the official design settles whether the payment-year settled row repeats the withholding amounts, because repeating them would count a withholding already paid through Modelo 123.

S05 outcome, 2026-09-24: not settled, so the block stays. RIRPF art. 94.1 settles that capital withholding arises at exigibility (or earlier payment) and art. 108.1 that it is declared in that period's Modelo 123, so it is declared in the accrual year. The 2025 record design requires full amounts in the accrual-year pendiente record (pp. 24-25) and sums every type-2 record into the declarant totals without exception (pp. 5-7), but states nothing about the amount fields of the payment-year record beyond reporting the recipient (p. 25) and the accrual year at 118-121 (p. 26). No AEAT note or INFORMA entry addresses it, and a search of the DGT binding and general rulings (eight queries, including the pendiente mechanism, the 999999999 placeholder and the accrual-year field) found none either: the nearest, V1292-05 and V4152-16, concern dividend attribution at exigibility and withholding on redistributed unclaimed dividends. The materialiser keeps the literal-design amounts with `filing_export_supported=False`, and S06 makes the open question visible on every settled row. The cited articles were re-read by anchor in the bundled RD 439/2007 extraction (`#a78`, `#a94`, `#a108`), whose units align with their headings; an earlier report of a one-heading offset was a misreading and was withdrawn.

<!-- First line after approval: `Approved yyyy-mm-dd`, written by the
orchestrator after establishing scoped authorization, including an explicit
advance authorization. Record its basis; ask only when it is absent. Then briefly describe the proposed work.
Reference `{adr}`s, `{research}`, `{reference}`. Supporting documentation
must be read when relevant. State the decision coverage assessment; when no
costly decision is involved and no ADR governs, say so. With several ADRs,
map their scope to Steps at L1 or the relevant containers at higher tiers. -->

## Steps

- [x] `S01` - add a per perceptor, clave, pending flag and accrual year row grouping plus a type-2 record count and base and withholding sum facts to the withholding bindings; `src/cadrumo/domain/calculations/registry/withholding_bindings.py`.
- [x] `S02` - compose the Modelo 193 annual source from the manual window and materialised pending and settled phase rows read from Modelo 123 retenciones, refusing allocation collisions and emitting contributor provenance; `src/cadrumo/application/aggregation/withholding_source.py`.
- [ ] `S03` - rebind the 2025 declarant totals to the type-2 record count and row sums and the perceptor rows to the new grouping, keeping the Modelo 123 relation as a reconciliation check, then queue the republish; `src/cadrumo/_data/registry/aeat/modelos/193/revisions/2025-y-siguientes/revision.toml`.
- [ ] `S04` - prove multi-source rows, exclusions, missing-store advisories, pull and calculate parity and 2025 export byte parity for one pending and one settled row; `src/cadrumo/application/aggregation/tests`.
- [x] `S05` - ground whether the payment-year settled row repeats the withholding amounts, and lift the filing-export block only when the official design settles it; `src/cadrumo/application/aggregation/m193_phase_materialization.py`.
- [ ] `S06` - attach a structured advisory naming modelo 193, the base and withholding fields and the missing-authority reason to every settled-prior-accrual row, so the unresolved payment-year amounts reach the handoff instead of reading as settled; `src/cadrumo/application/aggregation/m193_phase_materialization.py`.
- [ ] `S07` - fail closed for a monthly withholding filer: when the canonical obligation schedule makes the filer's Modelo 111 or 123 monthly, refuse capture into a quarterly window and have the 190 and 193 annual sources return a structured refusal naming the modelo, the monthly periods and the reason instead of a quarterly-only total, proven with a monthly filer; `src/cadrumo/application/aggregation/withholding_source.py and the three capture producers`.
- [ ] `S08` - support monthly withholding filers end to end: place captured withholding in the filer's monthly window through the canonical period vocabulary and schedule, read monthly and quarterly windows in the 190 and 193 annual sources, and remove the S07 refusal; `src/cadrumo/application/aggregation and the retencion observations adapter`.

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

<!-- State which Steps, Phases, or Waves can be executed in parallel and
which carry hard ordering. At `L1` and `L2`, parallelism is decided
per-Step or per-Phase. At `L3` and `L4`, Waves are sequenced by
default (one Wave must land before the next can begin); Phases
within a single Wave may be parallelized when they share no hard
interdependency. -->

S01 and S02 can proceed in parallel on disjoint files. S03 depends on S01's grouping and facts existing in code, and its runtime effect waits for the republish. S04 depends on S01 through S03 being published. S05 is independent research and can run at any time, but its code change lands last.

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

- The Modelo 193 calculation for 2025 includes a pending row in its accrual year and a settled row in its payment year from captured capital withholding, through the real resolver and published authority, with no second summation path.
- The declarant's perceptor total equals the type-2 record count and its base and withholding totals equal the type-2 row sums.
- Exclusion cases hold: key C, a same-year payment and a 2026 accrual never produce phase rows; a missing store keeps its advisory.
- Pull and calculate agree, and the 2025 export matches the official record structure byte for byte at positions 117 and 118-121 on 500-byte records.
- Filing export stays blocked unless S05 grounds the settled row's amounts in the official design.
