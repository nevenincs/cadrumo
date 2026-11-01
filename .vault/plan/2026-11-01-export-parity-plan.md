---
tags:
  - '#plan'
  - '#export-parity'
date: '2026-11-01'
tier: L2
related:
  - '[[2026-09-27-export-parity-renta-withholding-sources-adr]]'
  - '[[2026-06-10-calculation-aggregation-taxonomy-adr]]'
  - '[[2026-06-26-binding-source-kind-taxonomy-unification-adr]]'
  - '[[2026-06-10-modelo-130-100-continuity-adr]]'
  - '[[2026-09-21-retenciones-workflow-observation-payment-contract-adr]]'
  - '[[2026-06-01-calculation-test-oracle-discipline-adr]]'
modified: '2026-11-01'
body_schema: body-v2
body_hash: 'sha256:ccf207134b0bf97c315ac107d9a3eb885d8ce4246dd6c1f10040c116466ef73f'
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
     Replace export-parity with a kebab-case feature tag, e.g. #foo-bar.
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

# `export-parity` plan

Make Modelo 100 credits (casillas 0592 to 0609) and the withholding sources behind them correct, traceable and reconciled, with the Python backend as the only calculation engine.

## Description

Approved 2026-11-01. Basis: the operator approved the proposed campaign in conversation on 2026-11-01 ("ok, thanks", replying to the campaign proposal and its request to proceed), after settling these rulings in the same session: advisory grade blocks export; suffered-withholding, reconciliation and resolution-record schemas are authorized with their design approved before code; the imputation criterion is a typed profile fact; borrador snapshots keep no backward compatibility; the 0604 fallback uses a typed original or complementaria filing kind; the taxonomy amendment is drafted now; datos fiscales manual import, live pull and the Modelo 193 manual-row gate are in scope. The operator also fixed agent routing: Haiku for read-only discovery, summaries and context packs, Sonnet for bounded code fixes, Opus for architecture, grounding and verdicts; behaviour is verified against the official rules throughout.

The work realises the accepted export-parity withholding-sources ADR, whose Step 1 (payer-side removal) is already done, and continues the 2026-11-01 work on branch `feature/renta-withholding`: commits 0348dcdf08, 5455dd4ec4, 3e691e76ad, 6bd819465e, 10dcf5c8fc and d13f60426e, plus the 0599 ledger binding held on `feature/renta-withholding-0599-ledger-binding` (d5493eed10) until the advisory grade exists.

Decision coverage. The export-parity ADR governs P02 to P07. P01 creates the missing decisions: a per-binding capability grade (new ADR, a public registry contract) for S14 and S05; a typed filing kind on captured observations (new ADR, persisted schema) for S16; the taxonomy amendment for S07; schema design as a reference plus an amendment to the export-parity ADR for P03 and P04; the imputation-criterion profile fact (research plus ADR) for P05; and the datos fiscales format grounding for P06. No Step after P01 executes on a decision that is not accepted. The Modelo 130 to 100 continuity ADR keeps 0604 on the relation channel; the binding-source-kind taxonomy ADR governs every new source or operation kind; the retenciones payment-contract ADR keeps payer-side stores out of every credit casilla; the oracle-discipline ADR governs every numeric assertion.

Out of scope: monthly withholding filers and monthly Modelo 123 (the tested refusal stays), new filing-grade promotions other than the S08 ruling, frontend, TUI and MCP code, IVA and other modelos, and the shared authority publication, which another session performs once.

## Steps

### Phase `P01` - Settle the campaign decisions

Draft and accept the decision records and grounding that every later Phase builds on; no product code.


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

- [ ] `P01.S01` - Draft the per-binding capability grade decision so an advisory value blocks verify and export but not calculation or preview; `.vault/adr/`.
- [ ] `P01.S02` - Draft the typed original or complementaria filing-kind decision for captured observations; `.vault/adr/`.
- [ ] `P01.S03` - Draft the aggregation-taxonomy amendment making tier divergence on filing-bound bindings a blocking finding; `.vault/adr/2026-06-10-calculation-aggregation-taxonomy-adr.md`.
- [ ] `P01.S12` - Ground and draft the suffered-withholding, reconciliation and resolution-record schemas as a code reference and an export-parity ADR amendment; `.vault/reference/ and .vault/adr/`.
- [ ] `P01.S13` - Ground the income imputation criterion in primary LIRPF, RIRPF, DGT and TEAC text and draft its profile-fact decision; `.vault/research/ and .vault/adr/`.
- [ ] `P01.S04` - Ground the AEAT datos fiscales download format against an official specimen or record design; `.vault/research/`.

### Phase `P02` - Build the grade, filing-kind and borrador foundations

Land the blocking advisory grade, the typed filing kind and the single borrador key contract that the evidence and reconciliation Phases rely on.

- [ ] `P02.S14` - Implement the per-binding capability grade and its export and verify block, applied to Modelo 130 casilla 06; `src/cadrumo/domain/calculations/registry/ and src/cadrumo/application/modelo/`.
- [ ] `P02.S05` - Rebase and merge the Modelo 100 casilla 0599 ledger binding under the advisory grade; `src/cadrumo/_data/registry/aeat/modelos/100/`.
- [ ] `P02.S16` - Capture the typed filing kind and let the 0604 fold prove casilla 18 zero for originals only; `src/cadrumo/application/live/ and src/cadrumo/domain/calculations/registry/observation_fold.py`.
- [ ] `P02.S15` - Project borrador imports through the bound-casilla map, refuse old snapshot keys and add terminal-origin classes; `src/cadrumo/application/live/borrador_100_import.py and src/cadrumo/application/modelo/borrador_binding.py`.

### Phase `P03` - Introduce the suffered-withholding evidence family

Give the Modelo 100 credit casillas a typed, encrypted per-payer evidence source enrolled in the canonical source mesh.

- [ ] `P03.S17` - Add the suffered-withholding namespace, record, source kind, validator and resolver with encrypted round-trip tests; `src/cadrumo/core/aggregation.py, src/cadrumo/application/aggregation/ and src/cadrumo/adapters/persistence/`.
- [ ] `P03.S18` - Add the certificate import flow under the app hierarchy; `src/cadrumo/entrypoints/cli/ and src/cadrumo/application/`.
- [ ] `P03.S06` - Fold the manual 0596 certificate binding into the family, move aeat_prefilled and bind 0596, 0597, 0598 and 0603 by semantic role; `src/cadrumo/_data/registry/aeat/modelos/100/`.

### Phase `P04` - Reconcile credit sources with blocking findings

Compare every credit casilla against its declared cross-check sources at cent precision and block filing on any open disagreement.

- [ ] `P04.S19` - Declare per-casilla value and cross-check sources and emit blocking reconciliation findings through verify, the CLI handoff and the report; `src/cadrumo/_data/registry/aeat/modelos/100/ and src/cadrumo/application/modelo/`.
- [ ] `P04.S20` - Add the operator resolution record keyed to the disputed amounts; `src/cadrumo/application/modelo/ and src/cadrumo/adapters/persistence/`.
- [ ] `P04.S07` - Make the precedence overlay report tier divergence and block under the taxonomy amendment; `src/cadrumo/application/aggregation/source_resolution_operations.py`.

### Phase `P05` - Impute activity income and withholding by the taxpayer's criterion

Key activity income and withholding by accrual or receipt date per the elected criterion, so 0599 and Modelo 130 casilla 06 credit the right year.

- [ ] `P05.S21` - Add the imputation-criterion profile fact and its wizard question; `src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml and src/cadrumo/application/wizard/`.
- [ ] `P05.S22` - Key ledger activity income and withholding by the criterion and surface accrued-but-unpaid withholding as a rectification finding; `src/cadrumo/application/aggregation/renta_income_ledger.py and _renta_income_evidence.py`.
- [ ] `P05.S08` - Present the 0599 filing-grade promotion for operator ruling; `.vault/adr/`.

### Phase `P06` - Ingest AEAT datos fiscales as a cross-check source

Read datos fiscales through a manual import and a read-only live pull into one content-addressed record that feeds the reconciliation only.

- [ ] `P06.S23` - Add the pinned datos fiscales parser and its encrypted record and source-byte namespaces; `src/cadrumo/adapters/inbound/ and src/cadrumo/adapters/persistence/`.
- [ ] `P06.S24` - Add the manual datos fiscales import with identity refusal and idempotent content-addressed capture; `src/cadrumo/application/live/ and src/cadrumo/entrypoints/cli/`.
- [ ] `P06.S09` - Feed the datos fiscales record into the credit reconciliation; `src/cadrumo/application/modelo/`.
- [ ] `P06.S10` - Add the read-only datos fiscales live pull behind the live-read gate; `src/cadrumo/adapters/outbound/aeat/sede/`.

### Phase `P07` - Close the campaign with personas and review

Prove the mixed personas end to end against independent oracles, close the remaining withholding gates and hand off for publication.

- [ ] `P07.S25` - Make manual prior-accrual Modelo 193 rows face the settled-amount export gate; `src/cadrumo/application/filing/ and src/cadrumo/application/modelo/`.
- [ ] `P07.S26` - Prove the employee, employee-autonomo and payer personas end to end with independent oracles and extend the income-tax journey to 0599; `src/cadrumo/entrypoints/tests/ and dev/acceptance/income_tax/`.
- [ ] `P07.S11` - Record the 1577 and 0598 follow-ups and hand off the touched modelos and revisions for authority publication; `.vault/plan/`.

## Parallelization

P01 Steps run in parallel as drafts, each by one Opus agent supported by Haiku context packs; S01 and S02 go first because they unblock P02. Hard ordering: S14 needs S01; S05 needs S14; S16 needs S02; S07 needs S03; P03 and P04 need S12; P05 needs S13; P06 needs S04, and S10 also needs the live-write guard owned by another domain plus one attended live session. Within P02, S16 and S15 may run in parallel with S14 because their write sets are disjoint. P06 parsing (S23) may run alongside P03 and P04; S09 needs S19. P07 runs last. Concurrent writers keep disjoint files, serialize Modelo 100 registry edits, and run gates on a quiet tree. One orchestrator commits each Step.

## Verification

- Every regulated rule a Step introduces cites the specific official provision, instruction or record design for the exact revision and period. Search snippets are not grounding. An ambiguous reading stays advisory or unsupported and is recorded as such.
- Every numeric assertion uses an independent, hand-derived or official oracle, and runs through the real resolver, calculation and export path. No test double replaces the behaviour under test.
- Absent, unknown, unsupported, advisory, not-applicable and proven-zero stay distinct. An advisory value never reaches an exported file, and a credit-casilla disagreement blocks verify and export, naming the casilla, each source and each amount.
- Payer-side returns (111, 115, 123, 180, 190, 193) never feed a credit casilla: the payer-side guard test and its defective fixtures pass.
- Personas (a) employee, (b) employee and autonomo with 15 and 7 per cent invoices and quarterly Modelo 130, and (c) persona (b) also filing 111, 115, 180 and 190 produce 0596, 0599, 0604 and 0609 equal to their oracles. The income-tax journey asserts 0599.
- For touched scopes: `just check-style`, `just check-format`, `just check-types` and `just check-import-boundaries` pass (or the documented lint-imports substitution where the known checker defect applies). The registry passes `dev.registry.conformance valid` and `just check-bindings` with no blocking finding. Source installation, publication and runtime adoption are reported separately.
- Each Phase closes with an independent review appended to the rolling audit. Critical and high findings reopen their Steps. The plan completes when every Step is closed and the final integrated review passes.
