---
tags:
  - '#plan'
  - '#year-literal-migration'
date: '2026-11-07'
tier: L1
related:
  - '[[2026-08-14-registry-temporal-coverage-adr]]'
modified: '2026-11-07'
body_schema: body-v2
body_hash: 'sha256:93aaeab57c77ec20a96f60183e605a43d604f94756dd92722f04947afb999bd3'
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
     Replace year-literal-migration with a kebab-case feature tag, e.g. #foo-bar.
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

# `year-literal-migration` plan

Remove every written year from code so the authority resolves every year and no behaviour can diverge by filing year.

## Description

Approved 2026-11-07. Basis: the operator ordered on 2026-11-07 that years are never hardcoded anywhere in the codebase and that the authority resolves every year, and the coordinator session paused the bulk test migration on the same day after the production batches, to free budget for desktop work. This plan records the remaining work so a later session can resume.

Decision coverage: the registry temporal coverage ADR governs the support envelope, edition projection and refusal below the floor; the supported-years section of the tax calculation domain rule states that years come only from `src/cadrumo/_data/registry/aeat/legal/supported-filing-years.toml`. No new costly decision is involved.

Enforcement is the AST gate `dev/quality/year_literals.py` (`just check-year-literals`, about one minute), with planted-defect tests in `dev/quality/tests/test_year_literals.py`. It runs in `.github/workflows/merge-gate.yml` only; it is not part of `build-native`, `gate-local` or any CMake target, so it stays red until the plan completes without blocking desktop builds. Its finding count on feature/tui at the pause is 18215 in 2657 modules, down from 25695 in 3454.

Batching method: run the gate on feature/tui, group the findings by module area, and cut batches of about 30 files, keeping production modules separate from tests. Step scopes above name the batch ids of the paused worklist and their finding counts at the pause; a resuming session regenerates the batch file lists from a fresh gate run rather than trusting these counts. Each batch runs in its own locked worktree on a `yearfix/<batch>` branch from feature/tui, using the root virtual environment with the worktree first on `PYTHONPATH` and the root authority read-only, and lands as one `--no-ff` merge after merging feature/tui into it and re-running its tests.

Canonical derivations: Python tests use `cadrumo.domain.calculations.registry.tests.authored_editions` (`filing_year_envelope`, `open_ended_revision`, `revision_covering`, `newest_authored_edition`, `supported_authored_exercises`, `split_exercise_revisions`, `filing_grade_exercises`, `revision_last_exercise`); dev tooling reads the pinned authority; the desktop frontend uses `native/desktop/frontend/src/dev/fixtureDates.ts` over the served year authority. Dates are built from the derived year, period tokens through `Period`, weekday and holiday cases through the calendar resolver, and official parsers read the year printed on the document. Hand-recorded official tables are paired by position with the authored exercises, never keyed by year; selecting test cases by the asserted property is forbidden; no suppressions, skips or year-keyed data files; ty, ruff and the gate must be clean per batch; no authority publish from a batch.

Known findings recorded during the migration and owned elsewhere: Modelo 100 2025 cites its annual order on nearly every casilla and on the declaration extraction profile; the Modelo 303 2022 generated export lacks the projection-row repeat; Modelo 390 has no 2026 export scenario; `filing_grade_exercises` raises for modelos that split one exercise across revisions; the frontend recording keys and invoice-preview payloads hold 2026 until the recording is regenerated; one Modelo 111 2026 domiciliation window keeps its authored date as a named discrepancy.

## Steps

- [x] `S01` - Landed: gate, posture resolver, holiday calendars, P001-P005, T001-T022, T027-T032, T049, T050, ty fixes, domiciliation cutoff fix; `dev/quality/year_literals.py`.
- [x] `S02` - Land P006 and P007 production date and period text; `dev/runtime_lifecycle`.
- [x] `S03` - Land the loader directory-mode support preamble and drop the three local preamble copies; `dev/registry/conformance/loader_directory_mode_support.py`.
- [ ] `S04` - Migrate T023-T025 registry tests (1329 findings); `dev/registry/tests`.
- [ ] `S05` - Migrate T026 release tests (79 findings); `dev/release`.
- [ ] `S06` - Migrate T033-T048 adapter tests (2905 findings); `src/cadrumo/adapters`.
- [ ] `S07` - Migrate T051-T081 application tests (4882 findings); `src/cadrumo/application`.
- [ ] `S08` - Migrate T082 and T127 core tests (226 findings); `src/cadrumo/core`.
- [ ] `S09` - Migrate T083-T096 domain tests (2750 findings); `src/cadrumo/domain`.
- [ ] `S10` - Migrate T097-T116 and T128 entrypoint tests (3771 findings); `src/cadrumo/entrypoints`.
- [ ] `S11` - Migrate T117 cadrumo package tests (61 findings); `src/cadrumo/tests`.
- [ ] `S12` - Migrate T118-T124 and T133-T135 runtime tests (1186 findings); `src/cadrumo_runtime`.
- [ ] `S13` - Migrate T125 and T136 adapter date text and T126 application tests (272 findings); `src/cadrumo/adapters`.
- [ ] `S14` - Migrate T129 packaging and T130 TUI dev tooling (29 findings); `dev/packaging`.
- [ ] `S15` - Migrate T131 frontend tests; calendarBusy.ts and its sweep stay with DESKTOP (147 findings); `native/desktop/frontend`.
- [ ] `S16` - Migrate T132 and T137 mixed tests (573 findings); `src`.
- [ ] `S17` - Second passes and follow-ups: nested year-pair gate rule, casilla helper reverts, recorded findings; `dev/quality/year_literals.py`.

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

Batches within and across Steps S04 to S16 are independent and may run two or three at a time in disjoint worktrees, with one integrator serialising the merges into feature/tui. A batch whose files import a shared support module owned by another batch merges feature/tui after that batch lands. S17 runs last. Registry data and `dev/registry` landings respect coordinator-announced registry freezes, and no landing touches another session's uncommitted files in the root.

## Verification

Each Step closes when the gate lists none of its files, its tests pass at the derived years with integration markers included, and ruff and ty are clean on its files. The plan is complete when `just check-year-literals` exits zero on feature/tui, `just check-types` stays clean, and the every-year deadline posture parity test passes across the support envelope.
