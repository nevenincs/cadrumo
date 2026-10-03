---
tags:
  - '#plan'
  - '#binding-consumer-closure'
date: '2026-10-02'
tier: L1
related:
  - '[[2026-09-11-binding-schema-adr]]'
  - '[[2026-07-05-modelo-720-row-carrier-adr]]'
modified: '2026-10-03'
body_schema: body-v2
body_hash: 'sha256:6c0589f840bb4403a8440463a804f8782a968761969f3d6e13035929d1cd434e'
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
     Replace binding-consumer-closure with a kebab-case feature tag, e.g. #foo-bar.
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

# `binding-consumer-closure` plan

Drive the bindings no casilla, formula or export names from 673 to zero by repairing each root cause, then make the residue a compiler refusal.

## Description

Approved 2026-10-02. Basis: the operator instructed this session to fix the root causes of the 673 unreferenced bindings, plug the holes, republish the authority and remeasure until the count is zero.

Measured on published generation `482b3124` (159 revisions, 10,261 binding rows): 673 rows, 595 distinct, carry no typed consumer in `binding_consumers` (`src/cadrumo/domain/calculations/registry/binding_targets.py`). Three root causes produce them. Declarations made before the first edition that consumes them (232 page bindings, 184 member rows, 390 rate bands, 303 rows). Declarations that outlived their consumer (390 2026 has no record design; 193 2025 dropped its formula). Declarations nothing ever consumed: duplicates of manual casillas (360), casillas naming a binding without `input_kind = "bound"` (232), rows of deferred provider kinds with no route (232, 360, 182), acquisitions mirrored by Python instead of the registry (349), a malformed export selector (347), unwired foreign-asset rows and baselines (720), and unwired calculation inputs (100, 130, 193, 200, 202, 210).

Decision coverage: the accepted binding-schema ADR governs. It already decides that the compiler refuses unreferenced bindings without an explicit disposition and that a deferred disposition must never become a silent gap; S08 completes that refusal. Removing a deferred-kind row is done only where a working canonical input path for the same positions remains (232 manual slots, 360 manual casillas) or the modelo is applicability-only (182). Each calculation or export wiring is grounded in the official AEAT/BOE source for its modelo and revision before it lands; where grounding is ambiguous the binding is retired with that evidence rather than wired by guess. A disposition (`non_calculation`) is used only when its reason and named consumer are literally true, never to silence a count.

## Steps

- [x] `S01` - Delete the 146 modelo 360 manual-input bindings that duplicate manual casillas at identical export positions, remove the work-form exact-wire dedupe that existed only to hide them, and regenerate the 360 form layout; `src/cadrumo/_data/registry/aeat/modelos/360/revisions/2010-y-siguientes/, src/cadrumo/application/modelo/work_form.py, src/cadrumo/application/modelo/tests/test_work_form_binding_labels.py, src/cadrumo/entrypoints/tests/test_modelo_wire_input_alias.py`.
- [x] `S02` - Retire the 173 export-only page bindings modelo 390 inherits into its 2026 edition, which declares no record design, and regenerate the 2026 form layout; `src/cadrumo/_data/registry/aeat/modelos/390/revisions/2026/`.
- [x] `S03` - Move every binding declared before the first edition that consumes it to that edition: modelo 232 page bindings 2016-2017 to 2018-y-siguientes, modelo 184 member rows 2022 to 2023-2024, modelo 390 2 and 7.5 percent rate bands 2022 to 2024, modelo 303 rows to their first consuming edition, and ground the modelo 390 0.62 percent recargo band against the 2022 design before moving or wiring it; `src/cadrumo/_data/registry/aeat/modelos/{232,184,390,303}/revisions/*/`.
- [x] `S04` - Close the modelo 232 related-party slot hole: keep the 45 vinculada casillas informational (Modelo232VinculadaRow detail rows fill them), drop the duplicate manual-input bindings their overrides named, and refuse any non-bound casilla that names a binding; `src/cadrumo/_data/registry/aeat/modelos/232/, dev/registry/compiler/validate_bindings.py, dev/registry/compiler/tests/`.
- [x] `S10` - Remove the unrouted deferred detail-row families the operator chose to retire: the 6 modelo 232 related_party_operation, 5 modelo 360 refund_operation and 15 modelo 182 donativo_donor row bindings, together with the provider kinds, registrations, observation models, row-set assemblers and tests that exist only to serve them, and declare the family dispositions and reasons their removal leaves; `src/cadrumo/_data/registry/aeat/modelos/{182,232,360}/, src/cadrumo/domain/calculations/registry/detail_record_bindings.py, src/cadrumo/domain/calculations/registry/donativo_bindings.py, src/cadrumo/domain/calculations/registry/binding_provider_registration.py, src/cadrumo/core/aggregation.py, src/cadrumo/application/calculations/row_set_assembly.py`.
- [x] `S05` - Express modelo 349 intra-community acquisitions through typed registry consumers, replacing the Python row mirror and wiring the four acquisition header totals and the ledger guard, grounded in the official 349 record design; `src/cadrumo/_data/registry/aeat/modelos/349/, src/cadrumo/domain/calculations/registry/_invoice_row_materialization.py, src/cadrumo/application/invoices/source_resolver.py, src/cadrumo/application/modelo/_m349_ledger_guard.py`.
- [ ] `S11` - Repair the modelo 347 declarant total bindings and wire them to the type 1 record, grounded in the official 347 record design; `src/cadrumo/_data/registry/aeat/modelos/347/`.
- [ ] `S12` - Render every modelo 347 signed amount as the record designs require (sign byte N or blank, 13 integer and 2 decimal digits) for the declarante total and the 12 declarado amounts in editions 2011-2024 and 2025-y-siguientes, through a reviewed signed-composite grammar in the export generator and render-profile rules grounded in aeat-dr-347-2011 and aeat-dr-347-2025, with byte-level export tests; authorized by the user (fix everything, 2026-10-02); `dev/registry/pipeline/render_profile.py, dev/registry/render_profiles/modelo_347/, src/cadrumo/_data/registry/aeat/modelos/347/revisions/*/export/`.
- [ ] `S06` - Compose the modelo 720 type 2 record per the 2026-10-02 row-carrier amendment (confirmed by the user on 2026-10-02 after review of the concrete rulings): persisted asset identity and join, class-routed row-field slots as registry data, source-owned lock precedence, ECB euro conversion at the legal rate date through the existing FX port with the frozen real-estate value and last-declaration baselines, type 1 totals from type 2, refusal of pre-identity stored revisions, and backend operations with a thin CLI, TUI parity and MCP envelope conformance; `src/cadrumo/_data/registry/aeat/modelos/720/, src/cadrumo/domain/foreign_assets/, src/cadrumo/application/foreign_assets/, src/cadrumo/adapters/persistence/profile/foreign_assets.py, src/cadrumo/domain/calculations/registry/detail_record_bindings.py, src/cadrumo/domain/calculations/registry/schema_exports.py, src/cadrumo/domain/calculations/registry/export.py, src/cadrumo/domain/currency/, src/cadrumo/adapters/outbound/fx/, src/cadrumo/application/aggregation/foreign_assets.py, src/cadrumo/application/aggregation/source_mesh.py, src/cadrumo/application/calculations/row_set_assembly.py, src/cadrumo/application/calculations/foreign_asset_redeclaration.py, src/cadrumo/application/filing/, src/cadrumo/application/modelo/, src/cadrumo/entrypoints/, dev/registry/compiler/`.
- [ ] `S07` - Ground and wire, or retire with evidence, the unconsumed calculation inputs of modelos 100 (2024 guarderia), 130 (cumulative ledger totals), 193 (2025 annual relation prefill), 200 (SAL reserva especial), 202 (INCN prior 12 months) and 210 (IRNR rendimientos integros); `src/cadrumo/_data/registry/aeat/modelos/{100,130,193,200,202,210}/`.
- [ ] `S08` - Promote the unreferenced-binding advisory to a compiler refusal with an isolated detector-teeth fixture, and fail the binding reference lane of the registry status report on any residue; `dev/registry/compiler/validate_bindings.py, dev/registry/analysis/registry_status.py, dev/registry/compiler/tests/, dev/registry/analysis/tests/`.
- [ ] `S09` - Regenerate every touched form layout through its owner, republish the authority, remeasure check-registry and check-bindings to zero unreferenced bindings, and run the owning registry and calculation tests; `src/cadrumo/_data/registry/aeat/modelos/*/revisions/*/form_layouts/, .authority/`.

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

One writer executes every Step in sequence; registry source, form layouts and the published authority are shared surfaces. Legal grounding research for S03, S05, S11, S06 and S07 may run ahead in a read-only research agent. S08 runs only after the corpus residue is zero, and S09 closes the plan after every corpus Step.

## Verification

- The unreferenced-binding advisory reports zero over a freshly published authority, measured by `just check-registry` (`unreferenced_bindings.total = 0`) and `just check-bindings` (`summary.unreferenced_bindings = 0`).
- The compiler refuses a synthetic unreferenced binding and a casilla that names a binding without `input_kind = "bound"`, each proven by an isolated fixture in the same suite as the passing corpus.
- Every touched generated form layout is regenerated by its owner and passes its integrity check; every touched export target stays current or keeps its honoured disposition.
- Each wiring change carries its official source reference and a focused test over the real registry and resolver; owning registry and calculation suites show no new failure against the recorded baseline.
- The final integrated review passes.
