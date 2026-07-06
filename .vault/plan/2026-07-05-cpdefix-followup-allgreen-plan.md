---
tags:
  - '#plan'
  - '#cpdefix-followup-allgreen'
date: '2026-07-05'
modified: '2026-07-06'
tier: L3
related:
  - '[[2026-06-30-cpdefix-calculation-allgreen-audit]]'
  - '[[2026-07-04-counterpart-source-provider-adr]]'
  - '[[2026-07-05-modelo-720-prior-year-baseline-plan]]'
  - '[[2026-07-05-cpdefix-followup-allgreen-research]]'
  - '[[2026-07-05-cpdefix-followup-allgreen-adr]]'
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
     Replace cpdefix-followup-allgreen with a kebab-case feature tag, e.g. #foo-bar.
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

# `cpdefix-followup-allgreen` plan

## Wave `W01` - Current Truth Refresh

Separate stale closeout blockers from live calculation risks before dispatching coders.

<!-- One-line headline summary plan. -->

### Phase `W01.P01` - Blocker Inventory

Refresh the cpdefix closeout ledger against current code, vault records, and focused gates.

- [x] `W01.P01.S01` - Record the current stale-versus-live blocker refresh from RAG and focused gates; `.vault/audit/2026-07-05-cpdefix-followup-allgreen-audit.md`.
- [x] `W01.P01.S02` - Reconcile the shared cpdefix testimonial ledger against any new first-level persona roots; `tmp/personas/`.

### Phase `W01.P02` - Agent Dispatch Hygiene

Keep future workers grounded, non-destructive, and scoped to current blockers rather than stale closeout residue.

- [x] `W01.P02.S03` - Brief future code-fixer agents with required vaultspec-rag grounding and no-reexport/no-destructive-git constraints; `.vault/exec/2026-07-05-cpdefix-followup-allgreen/`.

## Wave `W02` - Calculation Edge Hardening

Work only the calculation edges that remain live after the truth refresh.

### Phase `W02.P03` - M347 Source Ownership

Keep M347 summary calculation on the current invoice-owned route unless a reserved-source provider trigger is explicitly approved.

- [x] `W02.P03.S04` - Prove the current M347 summary route remains invoice-owned and does not falsely promote reserved counterpart sources; `src/aeat/_data/registry/aeat/modelos/347/revisions/2008-y-siguientes/`.
- [x] `W02.P03.S05` - Defer repository-backed counterpart provider enrollment until a ledger or purchase-evidence binding trigger is approved; `src/aeat/application/aggregation/_counterpart.py`.

### Phase `W02.P04` - Deferred Source Review

Audit remaining deferred and reserved source-kind edges so live registry declarations never resolve silently blank.

- [x] `W02.P04.S06` - Audit current deferred and reserved source-kind partitions for registry-declared but unenrolled sources; `src/aeat/application/aggregation/_source_mesh.py`.
- [x] `W02.P04.S07` - Select the next triggered deferred detail-row family only if a current persona or operator filing need requires it; `.vault/audit/`.

## Wave `W03` - Verification and Closure

Convert refreshed findings into reproducible gate evidence before making any allgreen claim.

### Phase `W03.P05` - Gate Ladder

Run narrow gates first, then broader calculation gates after live blockers are reconciled.

- [x] `W03.P05.S08` - Run focused gates for import hygiene, source enrollment, M720 row carrier, and M347 counterpart-summary behavior; `src/aeat/tests/`.
- [x] `W03.P05.S09` - Run scoped calculation application and registry test gates before making any allgreen claim; `src/aeat/application/`.

### Phase `W03.P06` - Evidence Closure

Keep the plan honest by pairing checked rows with exec records and vault health evidence.

- [x] `W03.P06.S10` - Scaffold step execution records for completed plan rows and attach verification evidence; `.vault/exec/2026-07-05-cpdefix-followup-allgreen/`.
- [x] `W03.P06.S11` - Regenerate the feature index and run vault checks for the follow-up plan; `.vault/index/`.

## Wave `W04` - Post-Completion M130 Gasto Parity

Reopen the campaign for the current-tree M130 gasto edge where explicit actividad-economica category evidence must not be lost when broader business classification has not yet caught up.

### Phase `W04.P07` - M130 Gasto Category Eligibility

Harden the Modelo 130 casilla 02 gasto path so explicit actividad-economica transaction evidence follows the same eligibility authority as the casilla 01 income path.

- [x] `W04.P07.S12` - Revalidate current M130 gasto actividad-economica eligibility against production aggregation; `src/aeat/application/aggregation/_renta_gasto_ledger.py`.
- [x] `W04.P07.S13` - Cover unclassified actividad-economica gasto and reviewed exclusion behavior with real aggregation tests; `src/aeat/application/aggregation/tests/test_renta_gasto_aggregation.py`.
- [x] `W04.P07.S14` - Record focused verification evidence for the post-completion M130 gasto edge; `.vault/exec/2026-07-05-cpdefix-followup-allgreen/`.

## Wave `W05` - Shared Worktree Resync

Reconcile cpdefix follow-up tracking after concurrent agents relocated source-mesh enrollment tests, preserving no-reexport import hygiene and focused verification evidence before further dispatch.

### Phase `W05.P08` - Relocated Source-Mesh Enrollment

Keep the moved regularizacion enrollment tests grounded on real source imports and verify their current mesh behavior without absorbing unrelated shared worktree edits.

- [x] `W05.P08.S15` - Verify relocated regularizacion source-mesh enrollment gates after the no-reexport cleanup; `src/aeat/application/modelo/tests/test_bienes_inversion_regularizacion_source_mesh_enrollment.py, src/aeat/application/modelo/tests/test_prorrata_regularizacion_source_mesh_enrollment.py`.
- [x] `W05.P08.S16` - Resync relocated regularizacion source-mesh enrollment tests and remove test-export repository import; `src/aeat/application/modelo/tests/test_bienes_inversion_regularizacion_source_mesh_enrollment.py`.

## Wave `W06` - No-Reexport Source Provision

Remove remaining campaign-owned test provisioning through the application adapter export bundle where a concrete real adapter source is available, preserving real-behavior gates for the calculation surface.

### Phase `W06.P09` - Bienes-Inversion Repository Source

Provision capital-goods regularizacion tests from the real bienes-inversion persistence adapter instead of the test-export bundle and verify the calculation/advisory behavior.

- [x] `W06.P09.S17` - Replace bienes-inversion test-export repository imports with the real persistence adapter source; `src/aeat/application/calculations/tests/test_bienes_inversion_regularizacion.py, src/aeat/application/modelo/tests/test_bienes_inversion_advisory.py`.
- [x] `W06.P09.S18` - Replace invoice test-export repository imports with the real persistence adapter source; `src/aeat/application/invoices/tests/test_bulk_import.py, src/aeat/application/filing/tests/test_source_mesh_review.py`.
- [x] `W06.P09.S19` - Replace memoized transaction test-export repository import with the real persistence adapter source; `src/aeat/application/modelo/tests/test_memoized_transaction_catalogue_repository.py`.
- [x] `W06.P09.S20` - Replace renta income aggregation test-export repository imports with real persistence adapter sources; `src/aeat/application/aggregation/tests/test_renta_income_source_jurisdiction_m100.py, src/aeat/application/aggregation/tests/test_impatriado_income_ledger.py`.
- [x] `W06.P09.S21` - Replace LLM telemetry test-export imports with real adapter sources; `src/aeat/application/ledger/tests/test_llm_classify_run_telemetry.py, src/aeat/application/tests/test_diagnostics_telemetry.py`.

## Description

<!-- Briefly describe the proposed work. Reference `{adr}`s,
`{research}`, `{reference}`. Supporting documentation must be read prior to
writing the plan document. -->

## Steps

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
