---
tags:
  - '#plan'
  - '#modelo-editor-workbench'
date: '2026-09-30'
tier: L2
related:
  - '[[2026-09-30-modelo-editor-workbench-adr]]'
  - '[[2026-09-30-modelo-editor-workbench-operator-layer-adr]]'
modified: '2026-09-30'
body_schema: body-v2
body_hash: 'sha256:db4ecc341b9619d4f3e67fe49415da84b382c5fbd166112ec85441dd0ded08d2'
---

# `modelo-editor-workbench` plan

Give every modelo a schema-derived editor workbench that keeps the operator's values, speaks the filer's language and files from one screen.

## Description

Approved 2026-09-30. Basis: the operator opened this session with the mission to redesign the
TUI modelo filing experience into a user-operable, schema-derived editor workbench for every
modelo, directed five parallel design investigations, and holds a standing advance authorization
for vault records, decision acceptance, plans and code in this repository.

The work turns the modelo workspace into one workbench per declaration. Every revision gets a
generated, validated form layout from the registry authority; an application read model joins
that layout with the canonical work review, the current calculation revision and the edit
admission into a classified, localized form; and the TUI renders it as a section navigator, a
virtual casilla list, a help band, a stepper and a review-gated staged edit session. The
prerequisite correctness work makes edits and recalculations keep the operator's values.

Decision coverage. `2026-09-30-modelo-editor-workbench-operator-layer-adr` governs P01.
`2026-09-30-modelo-editor-workbench-adr` governs P02 to P05: D1 governs P02, D2 and D7 govern
P03, D3 to D6 govern P04, and D8 governs P05 and the delivery order. Both records amend accepted
decisions they name (form projection, workspace interface D1 and D6, edit contract D2); every
other clause of `2026-08-24-tui-modelo-workspace-interface-adr`,
`2026-08-24-modelo-edit-contract-adr`, `2026-09-07-tuimodelo-form-projection-adr` and
`2026-08-10-casilla-schema-read-model-adr` stands and binds these Steps. The evidence is the
feature's reference and its five research records.

This plan absorbs, for the modelo editor, the open `2026-09-07-tuimodelo-plan` Steps it
supersedes in scope: W03.P09 (value handling), W03.P10 to W03.P13 (declared form projection)
and W05.P17 (casilla editor). Those rows stay in their plan and are annotated when this plan
closes them. A concurrent session owns `2026-09-23-tui-registry-api-gate-plan` in this worktree;
its files (`workspace.py`, `workspace_producers.py`, `work_review.py`) are not edited here.

## Steps

### Phase `P01` - edit correctness and the operator layer

Make every edit and recalculation keep the operator's values, give every value a typed parser, and admit edits lazily with a renewable, work-unit-scoped baseline.

- [ ] `P01.S01` - Add the typed operator layer to the calculation revision as an optional identity axis that leaves every stored revision id unchanged, with forward-only load of revisions that lack it; `src/cadrumo/domain/modelos/calculation_revision.py`.
- [ ] `P01.S02` - Persist the caller tier as the operator layer when a revision is calculated from operator inputs, and add the one caller-context helper that reads operator layer, detail rows, filing-instance evidence, Modelo 210 fields and borrador snapshot from a revision; `src/cadrumo/application/modelo/calculation_actions.py`.
- [ ] `P01.S03` - Rebuild the edit executor on the current head's caller context so absent intents keep their values, clear and restore become real, 303 evidence is replayed, refusals are typed and execution leaves the event loop; `src/cadrumo/application/modelo/_edit_execution.py`.
- [ ] `P01.S04` - Replay the current head's caller context in the TUI calculate operation so recalculation keeps the operator's values and detail rows; `src/cadrumo/application/modelo/operation_definitions.py`.
- [ ] `P01.S05` - Author the typed edit value grammar and locale-aware parser, project the grammar onto writable admission entries, route booleans through the decimal channel, and bound only money addresses on the wire; `src/cadrumo/application/modelo/edit_parsing.py`.
- [ ] `P01.S06` - Correct admission: lazy admission with silent renewal, work-unit-scoped coordinates, refusal instead of raise below filing grade, non-writable row-field templates and channel-less types, and writable carry-source overrides; `src/cadrumo/application/modelo/edit_admission.py`.
- [ ] `P01.S07` - Add the in-process edit preflight that names addresses for required-empty warnings, override warnings and source-fed clear refusals; `src/cadrumo/application/modelo/edit_preflight.py`.
- [ ] `P01.S08` - Give the lifecycle door typed set, clear and restore intents, a lazy admission callable and a surfaced admission refusal, updating its composition in the launcher; `src/cadrumo/entrypoints/tui/modelo/lifecycle.py`.

### Phase `P02` - declared form layout family

Give every modelo revision a generated, validated form layout published with the registry authority.

- [ ] `P02.S09` - Define the form layout family: pages, sections, field, grid, repeating and binding-input blocks, placements with the unplaced arm, box numbers, aliases, design constants, review state and source digest; `src/cadrumo/domain/calculations/registry/schema_form_layouts.py`.
- [ ] `P02.S10` - Enrol the layout family on the modelo revision with its keyed-family policy, loader, compiler path and a validator in the registry dispatch that refuses omitted, duplicated, invented or stale placements; `src/cadrumo/domain/calculations/registry/schema.py`.
- [ ] `P02.S11` - Build the modelo-independent layout generator over export offsets joined to record designs, the modelo 100 dictionary and schema, design box numbers and casilla numbers, fixing the record-design heading reader it depends on; `dev/registry/form_layout`.
- [ ] `P02.S12` - Generate layouts for every revision and add the coverage report and the cross-edition stability gate; `src/cadrumo/_data/registry/aeat/modelos`.
- [ ] `P02.S13` - Author the shared grid column vocabulary and the heading keys of the most-filed modelos in all four locales through the catalogue workflow; `src/cadrumo/locales`.
- [ ] `P02.S14` - Republish the registry authority with the layout family and prove the runtime reader serves it; `src/cadrumo/domain/calculations/registry/authority.py`.

### Phase `P03` - form read model

Join the canonical review, the declared layout, the current revision and the edit admission into one classified, localized editor form.

- [x] `P03.S15` - Lift the locale number formats into a shared presentation formatter for money, ratio, decimal, integer, boolean, date and masked IBAN values; `src/cadrumo/application/modelo/value_presentation.py`.
- [x] `P03.S16` - Add the total source-kind policy table with family, override policy and destination, bound by test to the calculation precedence ladder; `src/cadrumo/application/modelo/source_policy.py`.
- [x] `P03.S17` - Build the editor form read model and builder with closed editability and origin enums, localized labels and help, counts, working figures, the unplaced list and the totality invariant; `src/cadrumo/application/modelo/work_form.py`.
- [ ] `P03.S18` - Assemble the help card parts from legal references, rendered formulas, official quotes, constraints and origin, treating label restatements as absent help; `src/cadrumo/application/modelo/casilla_help.py`.
- [ ] `P03.S19` - Add the form loading service and the before-and-after calculation diff query that the workbench door calls off the event loop; `src/cadrumo/application/modelo/work_form_service.py`.

### Phase `P04` - modelo workbench

Replace the page-per-destination workspace with one workbench per declaration built on the form read model.

- [x] `P04.S20` - Retire shipped glyphs missing from the pinned font and add a gate that keeps every shipped glyph inside it; `src/cadrumo/entrypoints/tui/components`.
- [ ] `P04.S21` - Build the virtual casilla list widget with the state vocabulary mapping, cursor anchored by casilla id and a totality and uniqueness guard; `src/cadrumo/entrypoints/tui/modelo/workbench/casilla_list.py`.
- [ ] `P04.S22` - Build the workbench screen: header with result and deadline, stepper and next action, section navigator, casilla list, help band and described footer keys; `src/cadrumo/entrypoints/tui/modelo/workbench/screen.py`.
- [ ] `P04.S23` - Add inline and detail editors over the parser grammar, the staged session, the review screen, the unsaved-change guard, apply through the operation modal, refresh in place and the result diff; `src/cadrumo/entrypoints/tui/modelo/workbench/editing.py`.
- [ ] `P04.S24` - Add the sources view with family grouping, states, drill-down and deep links to the owning source surfaces; `src/cadrumo/entrypoints/tui/modelo/workbench/sources.py`.
- [ ] `P04.S25` - Retire the page-per-destination workspace and its route factories atomically and route declarations to the workbench; `src/cadrumo/entrypoints/tui/modelo`.
- [ ] `P04.S26` - Author the workbench catalogue keys in all four locales and rewrite the remaining developer-language workspace strings; `src/cadrumo/locales`.

### Phase `P05` - acceptance and review

Prove the workbench across locales, geometries and themes through the production composition, render the visual review and close the plan review.

- [ ] `P05.S27` - Prove the workbench through the production composition in four locales, three geometries and two themes, with token-leak, focus-return and sensitive non-retention assertions; `src/cadrumo/entrypoints/tui/modelo/workbench/tests`.
- [ ] `P05.S28` - Render the sequence-backed visual review of the workbench and record before and after captures; `dev/tui`.
- [ ] `P05.S29` - Update the user documentation for filing a modelo in the TUI; `docs`.
- [ ] `P05.S30` - Run the plan-close review of the integrated workbench against both decisions and resolve its findings; `.vault/audit`.

## Parallelization

P01 and P02 run in parallel as two isolated lanes, each in its own git worktree on its own
branch, because both edit modules inside the registry authority compiler closure, which must not
sit uncommitted in the shared worktree while a republish could run.

- Lane edit-correctness owns P01. Write scope: `src/cadrumo/domain/modelos/calculation_revision*.py`,
  `src/cadrumo/application/modelo/{calculation_actions,calculation_resolution,_edit_execution,edit_admission,edit_services,edit_models,operation_definitions}.py`,
  new `edit_parsing.py`, `edit_value_grammar.py`, `edit_preflight.py`,
  `src/cadrumo/entrypoints/tui/modelo/lifecycle.py`, the `_modelo_lifecycle_door` function of
  `src/cadrumo/entrypoints/tui/launcher.py`, their tests and the `errors` catalogue keys they
  need.
- Lane layout-family owns P02. Write scope: `src/cadrumo/domain/calculations/registry/`,
  `dev/registry/`, `src/cadrumo/_data/registry/`, the `modelo` catalogue shards and their tests.
  It publishes its own authority in its worktree; S14's republish in the shared worktree waits for
  a quiet window with no concurrent sequence render.
- The orchestrator owns P03 and P04 in the shared worktree, on new modules, and merges each lane
  branch when its Phase closes. S17 and S19 consume P01's operator layer and P02's layout types,
  so their tests wait for both merges; S15, S16, S18 and S20 do not.

P05 starts after P04 closes. Commits use explicit pathspecs; no lane edits another lane's files.

## Verification

- P01: a second edit, a clear, a restore and a recalculation each keep every operator value
  they did not address, proven on real encrypted storage for modelos 130 and 303; the parser
  accepts and refuses the documented lexemes in all four locales; an apply more than five minutes
  after admission succeeds when nothing changed.
- P02: the validator refuses a layout that omits, duplicates or invents a casilla (proven on an
  isolated fixture); the generator places every casilla of every revision exactly once or declares
  it unplaced with a reason; the republished authority serves the layouts through the runtime
  reader; the coverage report is published.
- P03: the form builder runs over every revision of the real compiled registry with its totality
  invariant holding; every origin and editability arm is exercised by a test; the source policy
  table is total over the binding source kinds and conforms to the precedence ladder.
- P04: the workbench opens a calculated declaration through the production composition for
  modelos 130, 303, 111 and 390; editing, review, apply, diff and refresh work keyboard-only; no
  old destination id remains referenced; every shipped glyph is in the pinned font.
- P05: the acceptance matrix passes in es, en, ca and hu at 80x24, 120x36 and 160x48 in both
  themes; the sequence-backed visual review renders the workbench; the plan-close review audit
  carries no open critical or high finding.

The plan is complete when every Step is closed and the plan-close review passes.
