---
tags:
  - '#plan'
  - '#modelo-editor-workbench'
date: '2026-09-30'
tier: L2
related:
  - '[[2026-09-30-modelo-editor-workbench-adr]]'
  - '[[2026-09-30-modelo-editor-workbench-operator-layer-adr]]'
modified: '2026-10-01'
body_schema: body-v2
body_hash: 'sha256:5af9bc3e71d7440914ff3f78328e65104b165849942cfa0a687268592e484b64'
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

- [x] `P01.S01` - Add the typed operator layer to the calculation revision as an optional identity axis that leaves every stored revision id unchanged, with forward-only load of revisions that lack it; `src/cadrumo/domain/modelos/calculation_revision.py`.
- [x] `P01.S02` - Persist the caller tier as the operator layer when a revision is calculated from operator inputs, and add the one caller-context helper that reads operator layer, detail rows, filing-instance evidence, Modelo 210 fields and borrador snapshot from a revision; `src/cadrumo/application/modelo/calculation_actions.py`.
- [x] `P01.S03` - Rebuild the edit executor on the current head's caller context so absent intents keep their values, clear and restore become real, 303 evidence is replayed, refusals are typed and execution leaves the event loop; `src/cadrumo/application/modelo/_edit_execution.py`.
- [x] `P01.S04` - Replay the current head's caller context in the TUI calculate operation so recalculation keeps the operator's values and detail rows; `src/cadrumo/application/modelo/operation_definitions.py`.
- [x] `P01.S05` - Author the typed edit value grammar and locale-aware parser, project the grammar onto writable admission entries, route booleans through the decimal channel, and bound only money addresses on the wire; `src/cadrumo/application/modelo/edit_parsing.py`.
- [x] `P01.S06` - Correct admission: lazy admission with silent renewal, work-unit-scoped coordinates, refusal instead of raise below filing grade, non-writable row-field templates and channel-less types, and writable carry-source overrides; `src/cadrumo/application/modelo/edit_admission.py`.
- [x] `P01.S07` - Add the in-process edit preflight that names addresses for required-empty warnings, override warnings and source-fed clear refusals; `src/cadrumo/application/modelo/edit_preflight.py`.
- [x] `P01.S08` - Give the lifecycle door typed set, clear and restore intents, a lazy admission callable and a surfaced admission refusal, updating its composition in the launcher; `src/cadrumo/entrypoints/tui/modelo/lifecycle.py`.

### Phase `P02` - declared form layout family

Give every modelo revision a generated, validated form layout published with the registry authority.

- [x] `P02.S09` - Define the form layout family: pages, sections, field, grid, repeating and binding-input blocks, placements with the unplaced arm, box numbers, aliases, design constants, review state and source digest; `src/cadrumo/domain/calculations/registry/schema_form_layouts.py`.
- [x] `P02.S10` - Enrol the layout family on the modelo revision with its keyed-family policy, loader, compiler path and a validator in the registry dispatch that refuses omitted, duplicated, invented or stale placements; `src/cadrumo/domain/calculations/registry/schema.py`.
- [x] `P02.S11` - Build the modelo-independent layout generator over export offsets joined to record designs, the modelo 100 dictionary and schema, design box numbers and casilla numbers, fixing the record-design heading reader it depends on; `dev/registry/form_layout`.
- [x] `P02.S12` - Generate layouts for every revision and add the coverage report and the cross-edition stability gate; `src/cadrumo/_data/registry/aeat/modelos`.
- [x] `P02.S13` - Author the shared grid column vocabulary and the heading keys of the most-filed modelos in all four locales through the catalogue workflow; `src/cadrumo/locales`.
- [x] `P02.S14` - Republish the registry authority with the layout family and prove the runtime reader serves it; `src/cadrumo/domain/calculations/registry/authority.py`.

### Phase `P03` - form read model

Join the canonical review, the declared layout, the current revision and the edit admission into one classified, localized editor form.

- [x] `P03.S15` - Lift the locale number formats into a shared presentation formatter for money, ratio, decimal, integer, boolean, date and masked IBAN values; `src/cadrumo/application/modelo/value_presentation.py`.
- [x] `P03.S16` - Add the total source-kind policy table with family, override policy and destination, bound by test to the calculation precedence ladder; `src/cadrumo/application/modelo/source_policy.py`.
- [x] `P03.S17` - Build the editor form read model and builder with closed editability and origin enums, localized labels and help, counts, working figures, the unplaced list and the totality invariant; `src/cadrumo/application/modelo/work_form.py`.
- [x] `P03.S18` - Assemble the help card parts from legal references, rendered formulas, official quotes, constraints and origin, treating label restatements as absent help; `src/cadrumo/application/modelo/casilla_help.py`.
- [x] `P03.S19` - Add the form loading service and the before-and-after calculation diff query that the workbench door calls off the event loop; `src/cadrumo/application/modelo/work_form_service.py`.

### Phase `P04` - modelo workbench

Replace the page-per-destination workspace with one workbench per declaration built on the form read model.

- [x] `P04.S20` - Retire shipped glyphs missing from the pinned font and add a gate that keeps every shipped glyph inside it; `src/cadrumo/entrypoints/tui/components`.
- [x] `P04.S21` - Build the virtual casilla list widget with the state vocabulary mapping, cursor anchored by casilla id and a totality and uniqueness guard; `src/cadrumo/entrypoints/tui/modelo/workbench/casilla_list.py`.
- [x] `P04.S22` - Build the workbench screen: header with result and deadline, stepper and next action, section navigator, casilla list, help band and described footer keys; `src/cadrumo/entrypoints/tui/modelo/workbench/screen.py`.
- [x] `P04.S23` - Add inline and detail editors over the parser grammar, the staged session, the review screen, the unsaved-change guard, apply through the operation modal, refresh in place and the result diff; `src/cadrumo/entrypoints/tui/modelo/workbench/editing.py`.
- [x] `P04.S24` - Add the sources view with family grouping, states, drill-down and deep links to the owning source surfaces; `src/cadrumo/entrypoints/tui/modelo/workbench/sources.py`.
- [x] `P04.S25` - Retire the page-per-destination workspace and its route factories atomically and route declarations to the workbench; `src/cadrumo/entrypoints/tui/modelo`.
- [x] `P04.S26` - Author the workbench catalogue keys in all four locales and rewrite the remaining developer-language workspace strings; `src/cadrumo/locales`.

### Phase `P05` - acceptance and review

Prove the workbench across locales, geometries and themes through the production composition, render the visual review and close the plan review.

- [x] `P05.S27` - Prove the workbench through the production composition in four locales, three geometries and two themes, with token-leak, focus-return and sensitive non-retention assertions; `src/cadrumo/entrypoints/tui/modelo/workbench/tests`.
- [ ] `P05.S28` - Render the sequence-backed visual review of the workbench and record before and after captures; `dev/tui`.
- [x] `P05.S29` - Update the user documentation for filing a modelo in the TUI; `docs`.
- [ ] `P05.S30` - Run the plan-close review of the integrated workbench against both decisions and resolve its findings; `.vault/audit`.

### Phase `P06` - filer experience convergence

Converge the workbench on the filer-facing design the UX session specified, one owner per file: the read model states origin sources, AEAT data provenance, deadline, result direction and filed state; rows, lists, header, browsing and the editor present them in the filer's words; assumed values hold the journey until confirmed.

- [x] `P06.S31` - Add origin source descriptors, AEAT data provenance, the filing deadline, the result direction and the recorded-filing state to the form read model, and reconcile required boxes with verification; `src/cadrumo/application/modelo/work_form.py`.
- [x] `P06.S32` - Render rows as the official form: full box numbers, units, wrapped labels and origin words from the read model; `src/cadrumo/entrypoints/tui/modelo/workbench/casilla_list.py`.
- [x] `P06.S33` - Group the findings list by attention level with what to do and a working Enter, and turn the sources view into a per-box map by origin; `src/cadrumo/entrypoints/tui/modelo/workbench/issues.py`.
- [x] `P06.S34` - Rewrite the findings catalogue and the workbench texts in the filer's words and one register; `src/cadrumo/locales`.
- [x] `P06.S35` - Show a permanent status header with result direction, deadline and attention chips, rename the steps, and add collapsible navigation, search, go-to-box and sort; `src/cadrumo/entrypoints/tui/modelo/workbench/screen.py`.
- [x] `P06.S36` - Let assumed values hold the journey until confirmed, with bulk confirm, save-and-next, and where-it-comes-from in the editor; `src/cadrumo/entrypoints/tui/modelo/workbench/editor.py`.
- [x] `P06.S37` - Render the converged workbench in the review previews after each wave and close the phase with a review; `dev/tui`.
- [x] `P06.S38` - Narrow assumed values to required or non-zero boxes, give findings a grounded action and level, and expose grounded rates for rate cells; `src/cadrumo/application/modelo/work_form.py`.
- [x] `P06.S39` - Show empty optional boxes without repeating themselves, keep legal citations whole, and word review effects by source family; `src/cadrumo/entrypoints/tui/modelo/workbench/casilla_list.py`.
- [x] `P06.S40` - Cap long box lists in the findings list, drop counts the chips already give, hide to-dos on recorded declarations, and name sources in the filer's words; `src/cadrumo/entrypoints/tui/modelo/workbench/issues.py`.
- [x] `P06.S41` - Dim pages that do not apply this period, merge duplicate navigator rows, scope bulk confirm to a page or section, and drop redundant help lines; `src/cadrumo/entrypoints/tui/modelo/workbench/screen.py`.
- [x] `P06.S42` - Drive the acceptance journeys through confirming assumed values and recording the filing; `dev/acceptance/income_tax/tui_journey.py`.
- [x] `P06.S43` - Keep raw identifiers out of finding sentences and put them behind technical details; `src/cadrumo/locales`.

### Phase `P07` - filer safety, honesty and the docked editor

Close what the combined render and the design verification found: nothing unconfirmed reaches AEAT, every finding and blocker reads in the filer's words and colour, rows never contradict their own state, and the box panel docks beside the list as the operator decided.

- [x] `P07.S44` - Withhold export and recording while assumed values remain, count the next step as the blockers do, and draw every blocker mark in the error colour; `src/cadrumo/entrypoints/tui/modelo/workbench/progress.py`.
- [x] `P07.S45` - Word finding facts at the render boundary, name repeated-row findings in the filer's words at the missing level, carry calculation diagnostics to the workbench, and name an unnamed input by the box it feeds; `src/cadrumo/application/modelo/work_form.py`.
- [x] `P07.S46` - Keep a held zero apart from an empty box, give rate values their unit, and word sources, panels and staged changes in the filer's terms; `src/cadrumo/entrypoints/tui/modelo/workbench/casilla_list.py`.
- [x] `P07.S47` - Dock the box panel at the foot of the workbench, with the dialog below thirty rows of height; `src/cadrumo/entrypoints/tui/modelo/workbench/editor.py`.
- [x] `P07.S48` - Show the chain from an edited box to the result; `src/cadrumo/entrypoints/tui/modelo/workbench/editor.py`.
- [x] `P07.S49` - Author official headings for Modelo 100, then 349; `src/cadrumo/_data/registry/aeat/modelos`.
- [ ] `P07.S50` - Render the phase in the review previews and close it with a review; `dev/tui`.
- [x] `P07.S51` - Apply the design lane's terminology, area-name and conformance packs across every catalogue and regenerate the tests and references they move; `src/cadrumo/locales`.
- [x] `P07.S52` - Keep calculation diagnostics from firing for sources that do not apply to the filer, then restore the deferred reasons to the filing block; `src/cadrumo/application/aggregation`.
- [ ] `P07.S62` - Declare the scale of Modelo 303's rate literals so the general rate row prints its rate, grounded in the record design; `src/cadrumo/_data/registry/aeat/modelos/303`.
- [ ] `P07.S63` - Show a calculated box's formula with its values in the editor, so a zero result says why; `src/cadrumo/application/modelo/casilla_help.py`.

### Phase `P08` - declarations list

Replace the declarations screens with one list grouped by what the filer must do, built on a declaration summary that never builds a form per row, and stop a declaration filed with AEAT outside Cadrumo from reading as overdue.

- [ ] `P08.S53` - Project one declaration summary per row with state, result, blocking count, verification and deadline, isolating each row's failure; `src/cadrumo/application/overview`.
- [ ] `P08.S54` - Show a period filed with AEAT but not linked to a declaration here as filed, not overdue, with a way to link it; `src/cadrumo/application/overview/calendar.py`.
- [ ] `P08.S55` - Draw the grouped declarations list with the two-step new-declaration picker, surfacing advised and undetermined modelos; `src/cadrumo/entrypoints/tui/declarations`.
- [ ] `P08.S56` - Render the declarations list in the review previews and close the phase with a review; `dev/tui`.
- [ ] `P08.S61` - Give each deduction document Cadrumo cannot record its own blocking finding that sends the filer to file another way, once the intra-community refusal reaches this branch from main; `src/cadrumo/application/modelo/verification_actions.py`.
- [ ] `P08.S64` - Name the binding inputs no casilla owns from their official descriptions in each modelo's schema catalogue, and read those names in the form; `src/cadrumo/application/modelo/work_form.py`.

### Phase `P09` - documentation and naming

Bring the user documentation, the workbench guide and Hungarian modelo names in line with the glossary, and keep technical identifiers out of filer-facing exports and summaries.

- [ ] `P09.S57` - Land the workbench guide and its translations against the shipped behaviour; `docs/how-to/fill-in-and-file-in-the-workbench.md`.
- [ ] `P09.S58` - Apply the reconciled documentation rewrite and its translations, and correct CLI output strings that still print internal words; `docs`.
- [ ] `P09.S59` - Name every modelo by its proper name in Hungarian without guessing suffixes; `src/cadrumo/locales/hu`.
- [ ] `P09.S60` - Keep hashes and identifiers behind technical details in exports, summaries and pickers, and pass period words instead of tokens; `src/cadrumo/entrypoints/tui`.

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

P06 runs in the shared worktree as parallel workers with disjoint write scopes; the orchestrator
reviews and commits each worker's files. None of these scopes is in the authority compiler
closure. The UX session writes specs and catalogue text and edits no file here.

- Wave 1, in parallel:
  - S31 owns `src/cadrumo/application/modelo/work_form*.py` and their tests.
  - S32 owns `casilla_list.py`, `vocabulary.py` and `page_items.py` under
    `src/cadrumo/entrypoints/tui/modelo/workbench/`, and their tests; its origin words wait for
    S31's descriptor.
  - S33 owns `issues.py` and `sources.py` in the same package, and their tests.
  - S34 changes only catalogue values, through `dev.locales set-batch`.
- Wave 2, after S31 lands:
  - S35 owns `screen.py`, `progress.py`, `wording.py` and `keys.py`.
  - S36 owns `editor.py`, `session.py` and a new bulk-confirm module.
- S37's preview worker owns `dev/tui/**`. It renders only in quiet windows the orchestrator
  declares, or from a frozen snapshot of a commit.

P07 runs three lanes in the shared worktree, one writer per file, serialising locale batches and
commits behind scratch locks:

- S44 owns `progress.py`, `screen.py`, `header.py`, `review.py`, `bulk_confirm.py`, `keys.py` and
  `wording.py` in the workbench package.
- S45 owns `src/cadrumo/application/modelo/**` and the workbench's `issues.py`.
- S46 owns the workbench's `casilla_list.py`, `grid.py`, `page_items.py`, `vocabulary.py`,
  `sources.py`, `editor.py`, `legend.py`, `navigator.py` and `search.py`.
- S47 and S48 follow once S44 and S46 land, since they rebuild the editor's container inside the
  screen. S49 follows once the three lanes land, because publishing registry authority changes
  what every lane's tests read. Wording that the design lane owns arrives as validated packs and
  is wired, not written, by the lanes.

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
