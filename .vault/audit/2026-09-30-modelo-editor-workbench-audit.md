---
tags:
  - '#audit'
  - '#modelo-editor-workbench'
date: '2026-09-30'
modified: '2026-10-02'
body_schema: 'body-v2'
body_hash: 'sha256:cac268edaefb86a204a6ae5c8da40b1d46761d0f207b27db5b37026218d73324'
related:
  - "[[2026-09-30-modelo-editor-workbench-plan]]"
---

# `modelo-editor-workbench` audit: `Plan-close review of the modelo editor workbench`

## Scope

The integrated workbench delivered by Steps P01.S01 to P04.S26 (commits `d3dd2d2741` to `7bf4ae255b`),
reviewed against `2026-09-30-modelo-editor-workbench-operator-layer-adr` and
`2026-09-30-modelo-editor-workbench-adr` by tracing the edit, recalculation, verification, sources
and retirement workflows across the application and TUI boundaries. Two findings were confirmed
with throwaway probes over real encrypted storage; the rest were confirmed by reading the code.
Discovery ran without semantic search. Each entry states whether this review's follow-up
resolved it.

## Findings

### operator-layer-unknown | critical | the first edit or recalculation on an unrecorded layer silently reset operator values

`src/cadrumo/application/modelo/_edit_execution.py:183` and the calculate executor start from the
known layer, which is empty when a revision records none (CLI calculations and every revision
stored before layers existed). A probe calculated casilla 06 = 100 through the CLI path, then
applied an edit that set only 08: 06 fell to 0 and the new layer was recorded as known. The
operator-layer ADR requires the first edit on such a revision to say so in its review. Resolved:
the review now runs the preflight and, when the head does not record the filer's entries, names
every box holding a value nobody is recorded as having typed and requires acknowledgement before
Apply (`src/cadrumo/entrypoints/tui/modelo/workbench/review.py`); recalculation asks the same
question first through the shared confirmation dialog
(`src/cadrumo/entrypoints/tui/modelo/workbench/screen.py`, `_calculate`). Proven by
`src/cadrumo/entrypoints/tui/modelo/workbench/tests/test_workbench_production_edits.py` over real
storage and `test_workbench_review_check.py`.

### override-addressing | high | every box offered as overridable refused every value

`src/cadrumo/application/modelo/work_form.py` offered bound casillas (for example Modelo 130 box
05, carried from earlier filings) as overridable, but the workbench parsed and submitted them at
the casilla address, which admission makes read-only. Resolved: `edit_address` in
`src/cadrumo/application/modelo/work_form_models.py` addresses an override to the binding that
feeds the box; parsing, staging and apply use it. The production test sets and restores a carried
box through the real admission, parser, preflight and edit executor.

### stale-session | high | a stale apply was a dead end and re-basing was missing

A stale refusal kept the staged changes against the old baseline, so every retry was refused.
Resolved: a stale preflight or a stale apply now reads the declaration again, re-bases the staged
changes on it (dropping those that no longer apply), marks the boxes that now read differently,
and re-opens the review requiring acknowledgement (`WorkbenchEditSession.rebase` in
`src/cadrumo/entrypoints/tui/modelo/workbench/session.py`).

### verification-findings | high | verification findings and readiness no longer reached the filer

The form carried no verification findings or verdict, findings without a casilla disappeared,
and an incomplete verification left the next step at verify with no reason. Resolved: the form
carries the latest verdict and every finding, blocking first (`ModeloFormIssue`); an unresolved
verification sends the next step to a findings list opened with `i`, which leads to each named box
(`src/cadrumo/entrypoints/tui/modelo/workbench/issues.py`).

### result-diff | high | S23 closed without its result diff

Resolved: after an apply or a recalculation the workbench compares the forms before and after and
lists every changed box grouped as the filer's change, recalculated, from the filer's sources, or
other (`src/cadrumo/entrypoints/tui/modelo/workbench/result.py`).

### retirement-atomicity | high | acceptance journeys still drove the retired workspace

`dev/acceptance/iva/installed_m303_evidence_journey.py`, `dev/acceptance/income_tax/tui_journey.py`,
`installed_tui_financial_child.py`, `installed_tui_continuations.py` and
`dev/acceptance/retenciones/installed_tui_withholding.py` targeted deleted widgets. Resolved in `0452b64dcd`: every journey drives the workbench's keys, export dialog, confirmation and result
statement, and no retired widget id or row key remains under `dev/`.

### sources-hub-reason | high | a carry override records no reason and no displaced value, and the sources view offers no edit actions

The persisted operator layer records neither a reason nor the source value an override displaced
(`src/cadrumo/domain/modelos/calculation_revision_operator_layer.py`), and the catalogue told the
filer to state why. The override stays disclosed as replacing its source until restored, and the
wording no longer promises a reason. Open: recording a reason and the displaced value changes the
persisted revision identity and needs a decision.

### generation-refresh | medium | workbench operations left Declarations and search stale

Resolved: every successful operation asks the product to capture a new generation off the event
loop (`refresh_product`).

### refusal-reasons | medium | admission refusals and not-writable reasons were dropped

Resolved: an admission refusal is shown as its registered message, and a box that cannot be edited
says why in the help band and the notice (`editability_text` in
`src/cadrumo/entrypoints/tui/modelo/workbench/vocabulary.py`).

### sensitive-entry | medium | an over-long entry leaked into validation errors and logs

Resolved: every edit-contract model hides its input in validation errors, and the editor stops
typing at the parser's bound (`MAX_EDIT_LEXEME_LENGTH`).

### transport-tokens | medium | boolean binding values showed their stored token

Resolved for yes-or-no bindings, which now read as their value. Open: enumerated binding values
still show their stored code.

### workbench-shape | medium | four steps, stacked grids, no technical drawer, modal-only editing

The stepper has four steps rather than five, grids render stacked, raw identifiers have no drawer,
and every edit opens the detail editor. Open; the header also names no deadline.

### cli-disclosure | medium | CLI help did not say its calculation drops values typed in the TUI

Resolved in `990208a835`: the calculate help says so in all four languages.

### dead-code | low | unused production surface

`renew_edit_baseline`, `official_page` and `modelo_work_form_changes` had no caller. The preflight,
the product refresh and the form comparison are now wired; `renew_edit_baseline` and
`official_page` remain unused.

### blank-by-rule | low | Modelo 130 boxes 13 to 19 read as "could not be calculated" when box 07 is negative

The engine leaves them empty by rule, and the form has no origin for a box blank by rule. Open.

### modelo-100-direction | medium | the Modelo 100 result has no grounded direction

The convergence read model derives the settlement direction from the codified tipo de declaración
rule (`src/cadrumo/core/result_disposition.py`) or the registry's result role. Modelo 100 box 0670
has a role but no declared sign convention, so its header can say neither "to pay" nor "to be
refunded". Open: ground the sign convention and any refund or payment split from the official
Renta design or instructions.

### registry-pipeline-deadlock | medium | publishing authority in a fresh checkout can hang on Windows

The preview worker found that `candidate_compile_process.exit_when_parent_exits` starts a thread
blocked in `sys.stdin.buffer.read()`, and validation then imports numpy through openpyxl while
extracting XLSX evidence (`dev/registry/validate_evidence.py:201`); the numpy extension load hangs
beside that thread. Reproduced standalone. It bites any checkout that must re-extract XLSX text.
Open, outside this feature: the registry pipeline's owner should import numpy/openpyxl before the
watcher thread starts or stop reading stdin in a blocking thread.

### money-declared-as-decimal | medium | Modelo 100 money boxes are declared decimal, so they render without a euro sign

124 Modelo 100 casilla declarations, such as box 0012 at
`src/cadrumo/_data/registry/aeat/modelos/100/revisions/2020/casillas/0001-declarations.toml:91`,
are `data_type = "decimal"` although their formulas round as money. Presentation must not add a
euro sign to a decimal. Open, for the registry's authoring owner, grounded in the AEAT record design.

### finding-facts-raw | medium | some finding placeholders still carry raw codes and period tokens

The findings rewrite (`8735cd5b25`) kept every placeholder its producer supplies. Several still
carry raw identifiers (binding, source-kind, reason and predicate codes, pipe-joined id lists) and
period tokens such as "0A" or "4T"; amounts render unformatted with "EUR" and dates as ISO. Open:
their producers should supply filer-facing facts, or the renderer should format typed amounts and
dates.

### calculation-diagnostics | low | non-blocking calculation diagnostics never reach the workbench

Unresolved outcomes and source issues persist on the revision and reach the form as verification
findings, but the non-blocking `source_diagnostics` returned with a calculation
(`src/cadrumo/application/modelo/calculation_actions.py:194`) are dropped at
`src/cadrumo/application/modelo/operation_definitions.py:478`. Open.

### required-rule-sharing | low | verification keeps a wider required check than the form

The form's "needs your input" set (`src/cadrumo/application/modelo/required_inputs.py`) excludes
detail-row templates, which their rows answer for; verification also checks those templates through
their rows (`src/cadrumo/application/modelo/verification_actions.py:1733`). Replacing
verification's loop with the form's set would drop that check and under-declare, so it stays.
Resolved as intended; a test proves the form and a real verification agree on the scalar set.

### informative-totals | low | informative modelos have no headline totals for the header

Modelos with no settlement box (349, 347, 190) could show a record count and total on the result
line, but the form carries neither, so the header shows nothing there. Open: a read-model
descriptor of the headline totals, grounded in each modelo's summary record.

### window-opens | low | the form does not say when the filing window opens

The form carries the last day to file but not the first, which matters for Renta before its
campaign opens. Open: expose the window start from the same calendar resolver the deadline uses.

### modelo-100-headings | medium | Modelo 100's layout has no official headings for its pages and sections

The declared layout for Modelo 100 carries registry element names ("DatosEconomicos/Resultados",
"calculoimpuestores", "rdtotrabajores") as headings. The workbench now refuses identifier-like
headings and falls back to "Page N, part M", and labels parts by box range as an interim, but
Renta is the modelo most filers use and needs its official headings. Open, for the layout family's
owner: author the official Renta headings.

### affects-chain | low | the editor names only the boxes a box feeds directly

The help card knows only direct formula targets, so the editor's "Affects" line cannot show the
chain to the result ("[07] to [12] to [19]"). Open: expose the path to the settlement box from the
help card, derived from the revision's formulas.

### grids-as-official-tables | medium | Modelo 303's rate grid still renders stacked

D1 and D4 require grids as the official rows and columns, falling back to stacked records only on
narrow terminals. 303's accrued-VAT grid still renders stacked with "General regime" repeated,
the largest remaining gap between the workbench and the official form. Open, part of the
workbench-shape finding.

### brand-error-hue | high | the TUI's brand colour was indistinguishable from its error colour

The UX session measured the terracotta primary within 2 to 4 degrees of hue of the error red and
1.2:1 to 1.5:1 in contrast, so headings and bars drawn in it read as errors and a real blocker
could not stand out; the light primary also missed AA as text. The operator chose a blue brand
for the TUI only, keeping terracotta for the docs site and PDF summaries. Resolved in the palette
commit; `src/cadrumo/entrypoints/tui/tests/test_theme_palette_contrast.py` holds the separation.

### printed-rate-scale | medium | Modelo 303 rate literals declare no scale, and two labels contradict them

Design-constant rate literals in 303 ("00400", "02100", "00175") carry no declared scale, so the
workbench shows a printed rate only where the literal itself says "%" or its export field declares
the scale; the rest show a dot. The labels of [157] ("at 0.5%") and [17] ("at 1.0%") contradict
their literals ("00175", "00000"). Open, for the registry's owner: declare the export scale of the
rate literals and correct the contradicting labels.

### type-gate | high | P06 added eight type-checker diagnostics

The P06 phase review found pyrefly rejecting integer bounds on the `Decimal` rates in
`src/cadrumo/application/modelo/work_form_models.py`, ty reading the harness panel checks in
`dev/tui/harness/sequences.py` as always true or false, and an untyped set in
`dev/tui/tests/test_tui_harness_colour.py`. Resolved in e07cb8d33b and ab8385cdeb; the type gate
is back to the seventeen diagnostics that predate the phase.

### attention-scale | medium | the navigator marks a section done while its list heading marks it missing

A section whose boxes wait on an import or a calculation reads as done in the navigator and as
needing input in the list, and `n` walks to boxes the filer cannot type into
(`src/cadrumo/entrypoints/tui/modelo/workbench/navigator.py:253`,
`src/cadrumo/entrypoints/tui/modelo/workbench/page_items.py:274`). Seen on 111, 303, 115, 100
and a calculated 130. Resolved in b48f9f6db8: one standing per origin in
`src/cadrumo/entrypoints/tui/modelo/workbench/vocabulary.py:200` serves the navigator, the list
headings, the grid row edge, `n` and the header; a waiting box is never marked done.

### filed-origin-words | medium | a filed declaration still asks the filer to confirm

On a 303 recorded as filed, an assumed box reads "Assumed, please confirm" on its row and in its
panel, and the sources map files it under Calculated
(`src/cadrumo/entrypoints/tui/modelo/workbench/casilla_list.py:1067`,
`src/cadrumo/entrypoints/tui/modelo/workbench/sources.py:273`). The D4 amendment already has a
filed declaration ask for nothing, so the wording follows it without a new decision. Resolved in
b48f9f6db8 and 1ffb77f6ea: rows, panel, help band, sources map and search say what the box holds.

### bulk-confirm-dead-end | medium | F8 on the confirm step can open an empty dialog with an untrue note

On a 131 whose only assumed value is a typed manual input, F8 lists no boxes and says boxes filled
from a source update from it (`src/cadrumo/entrypoints/tui/modelo/workbench/bulk_confirm.py:42`,
`src/cadrumo/application/modelo/work_form.py:491`). Resolved in 630c000efd: one `confirmable`
rule in `src/cadrumo/application/modelo/work_form_models.py` admits typed binding inputs, a binding
amount reads as a number, and with nothing confirmable F8 opens the box's panel.

### issues-levels | low | the findings list has no missing level and counts pages that do not apply

Missing boxes the header counts are not listed, and assumed boxes on a page that does not apply
this period are listed but not counted (`src/cadrumo/entrypoints/tui/modelo/workbench/issues.py:75`).
Resolved in b48f9f6db8: a missing level, drawn from the boxes the header counts.

### rate-before-value | low | a rate box shows its grounded rate in place of its own value

For a rate box that is not a design constant, the grounded rate hides the box's value, including
a typed or failed one (`src/cadrumo/entrypoints/tui/modelo/workbench/casilla_list.py:340`). The
preview shows the grid's rate cells inconsistent as well: [154] "0.00" and [169] "0" beside
"2 %". Resolved in b48f9f6db8: only a design constant shows its rate as its value.

### grid-row-labels | low | the 303 grid's rate bands have no row label at full width

At full width the rows below [150] leave the label column empty, while the narrow fallback names
them ("General regime · 2 %"). Resolved in b48f9f6db8.

### unnamed-boxes | medium | Modelo 390's first-page boxes show their registry ids as labels

Thirty-two preview frames of 390 show labels such as
"modelo-390.page_1.sujeto-pasivo-registro-de-devolucion-mensual"; their panel says no explanation
exists and that dates and years cannot be entered, for what reads as a registration flag. Resolved at
the read model in 630c000efd: the label is absent from the registry, whose binding definitions
carry no label (`src/cadrumo/domain/calculations/registry/schema.py:281`), and 6,621 binding
inputs no casilla owns now read "Unnamed box" (714: 3,884; 369: 1,413; 390: 707; 353: 166;
131: 150; 360: 146; 232: 140; 720: 11; 100: 4). The panel's "dates and years" reason was a
free-text input's and now names values of this kind. Open for the registry's owner: a label and
help key on binding definitions, 390 and 131 first. Open for the workbench: name an input that
feeds exactly one casilla after that casilla before falling back.

### blocker-preview | low | no documented sequence produces a blocking finding

Every sequence golden verifies complete, so no preview shows a row, section or findings group
marked as blocking, and the error colour against the blue brand cannot be judged on a real
blocker. The documented sequence `verification-reports-blocked` (c8acf88c5d) and its preview scenario
(77752aa749) now produce one; the render is pending.

### year-and-date-channels | medium | manual year and date boxes can be neither typed nor confirmed

The calculation refuses a year casilla input (`src/cadrumo/application/modelo/_registry_helpers.py:67`
accepts decimal, money, integer and ratio only), and no layer carries a date. Proven on a real 136.
None of the required manual year or date boxes in 190, 193, 270, 349 and 360 can hold an assumed
value today, so no journey is stuck on one. Open for the calculation boundary.

### negative-yield-boxes | low | Modelo 130's later boxes are filled when the net yield is negative

The S25 note that boxes 13 to 19 stay empty when a result is negative did not reproduce: with
[03] = -500.00 and with [07] = -150.00 they are all filled (sequence
`first-quarter-expenses-exceed-income`). Withdrawn.

### verify-crash-missing-invoice | high | verification crashes on a deductible expense without its invoice

Outside this plan's changes, found while authoring sequences: a deductible expense added with
`ledger add` and no invoice evidence, then a 303 calculated and verified, ends verify with exit 6
`INTERNAL_CLI_UNEXPECTED_BOUNDARY` instead of a blocking finding; reproduced twice. Open for the
verification owner.

### ledger-drift-coverage | high | a sale added after calculating is not seen by verification

Outside this plan's changes: verification reports drift only for entries changed or removed after
the calculation, so a sale added afterwards is granted complete on the old figures, a silent
under-declaration. A recalculation after archiving a duplicate row still reported drift, possibly
from a reused revision snapshot (unconfirmed), and correcting one sale's price reads "0 entries
changed and 1 removed". Open for the verification owner.

### docs-build-warnings | low | two nitpicky build warnings predate this phase

The nitpicky docs build also reports `summary_layout` failing to import under the mocked
`reportlab`, and an unterminated inline literal at a docstring's line 16 that no module changed
on this branch carries (checked by a napoleon-aware scan shown to catch a planted case). The
phase's own warning, a rate unit read as a type, is fixed in aaec46451a. Open for their owners.

### main-stale-tests | medium | five tests fail on main itself after its registry changes

Measured on a detached copy of origin/main at cb6cd50ad8 on 2026-10-01: the same five tests fail
there as on this branch, whose test files are identical and whose only registry difference is
added form layouts. `test_modelo_303_special_case_casilla_routing` feeds 42 into a binding no
ledger can drive alone while the registry correctly sums the deduction boxes into [45] (the 2025
record design and the AEAT IVA manual's worked example); `test_cross_period_clean_state` still
encodes the Modelo 100 withholding dependencies an accepted decision removed;
`test_modelo_requires_data_inventory` expects bindings that only a computed casilla reads; and
`test_unrouted_iva_quantity_screen` predates the import base binding. Open for main, through a
pull request.

### intra-eu-deduction-hold-back | high | an intra-community acquisition cannot be filed, and checking it crashes

`docs/how-to/ledger-evidence.md:98` says an `intra_eu_current` deduction row cannot be
substantiated from the ledger and is held back. If so, its self-assessed VAT reaches 303 box [11]
while [37] stays at zero, overstating the VAT payable, unless the filer is told. Being checked in
the producer step; on main as well.

Measured 2026-10-01 through the real 303 2025 1T calculation with a synthetic intra-community
acquisition: the payable is not overstated, because the whole row is held back and [10], [11],
[36] and [37] all stay at zero. But no command can record the `intra_eu_self_assessment`
evidence the row needs (`src/cadrumo/application/ledger/actions_manual.py:1465`), so the
declaration can never pass; export refuses it (`src/cadrumo/application/modelo/export.py:491`),
and verification crashes with an undeclared precondition identity
(`src/cadrumo/application/modelo/verification_actions.py:1427`, refused at
`preconditions.py:535`) instead of a worded refusal. Open: declare the identity, give the filer a
way to record the evidence, and correct `docs/how-to/ledger-evidence.md:98`.

### concurrent-checkpoints | low | an integration session commits the shared tree while lanes work

Checkpoints 421f48dd30, 4a9190c8fc, 19eecd8355 and eaac53fd5b and the merges of main swept
lanes' uncommitted work into history, one of them while a file was mid-edit. Nothing was lost;
lanes verify their files against HEAD before each commit and report which commit holds their
work.

### m303-result-route | high | Modelo 303 can export a [27] its printed boxes do not add up to

The chain shown in the editor (2588ffa2ac) follows the registry's formula graph, and on 303 the
printed VAT amounts [03], [06], [09] and the total [27] reach no result: [46] is computed from
separate unprinted figures, while the official design sums [27] from the amounts and [46] from
[27] less [45]. The editor states that these boxes do not change the result, which is true of
the engine and not of the form. Verified on 2026-10-01: no printed amount box from [01] to [71]
can be overridden (each is bound, calculated or a design constant, and the edit executor, the
calculation inputs and the CLI binding override all refuse), and every box a filer can type keeps
[46] = [27] - [45] and [71] = [69] - [70] + [109] (- [112] from 2026). The editor now says the
calculation does not link such a box (069ae8ec92), which is accurate.

The verification found a different route that does break the printed sums: the autoconsumo del
promotor base (`aeat app modelo work calculate --autoconsumo-promotor-base`, or the profile fact
`iva.autoconsumo_promotor_base`) adds its cuota to [27] through `iva.cuota-devengada-total`
(`src/cadrumo/_data/registry/aeat/modelos/303/revisions/2022/formulas/0001-declarations.toml:1`,
extended at `2023/revision.toml:1463`) while no printed box carries it
(`2023/casillas/0001-declarations.toml:51`). With a base of 1000 on a synthetic 2025 1T ledger,
verification granted complete and the export wrote [09] 2100.00 and [27] 2310.00 with every
other [27] summand at zero, against the record design's [27] sum
(`06-303-ejercicio-2025-...extracted.md:104`). No check refused it and the filer was not told.
Open for the registry's owner, on main as well: route the autoconsumo base and cuota through the
printed rate boxes the instructions assign, grounded in AEAT text the corpus does not yet hold,
and add a check that [27] equals its printed summands.

### filed-elsewhere-overdue | high | a declaration filed with AEAT outside Cadrumo can still read as overdue

A Sede observation clears a period only when its justificante reconciles into the filing chain
(`src/cadrumo/application/live/filed_observation_persistence.py:268`). Otherwise the calendar
status is date-only (`src/cadrumo/application/overview/calendar.py:925`) and the evidence adds only
a badge (`src/cadrumo/application/overview/_calendar_evidence_sources.py:257`), so a period AEAT
has accepted reads Overdue when no justificante matched, the chain identity differs, the
reconciliation is unverifiable, or the row is not an active registration. The blocking findings
send filers to file another way, which lands in exactly this case. Planned as a step of the
declarations phase.

### check-route-dead-end | high | the workbench withholds the check that alone clears a check-route note

P07 phase review, 2026-10-01. Check-route reasons (`withholding_detail_absent` and the two IVA
evidence failures) block in the workbench (`src/cadrumo/application/modelo/calculation_notes.py:57`)
while the next step only offers to resolve them (`src/cadrumo/entrypoints/tui/modelo/workbench/progress.py:243`),
so an attested empty Modelo 190 withholding detail stays withheld for good although the check
would accept it. D4 leaves these reasons to the check. Being fixed: the check is offered while they
are the only blockers, and a report for the calculation decides them.

### printed-box-rule | medium | three definitions of a printed box disagree with the layout

`calculation_notes.py:160`, `work_form.py:416` and `casilla_help.py:373` each decide what is printed;
the gate's copy ignores the layout's box numbers, so 125 numbered boxes across 122 revisions,
Modelo 390's bound [53], [600], [602] and [36] among them, would warn instead of block when
unresolved. Being fixed with one resolver.

### confirm-chip | medium | calculation notes asked for a confirmation nothing can give

Notes at the confirm level counted in the header's confirm chip (`header.py:410`) with no confirm
action and no effect on the gate. Being moved to worth checking.

### p07-review-lows | low | stale verdict, a timing-dependent dock scroll, duplicate notes, stale docstrings

A stale calculation plus a missing box read incomplete instead of blocked
(`verification_actions.py:2131`); the docked panel's following-row scroll can run before the list
scrolls (`screen.py:1567`); three producers emit box-less unresolved notes beside staging's boxed
ones; and three docstrings or fields describe behaviour the code no longer has. Being fixed.

### binding-input-registry-notes | low | naming the unowned inputs surfaced registry modelling questions

Naming the 2,850 placed binding inputs no casilla owns from their record designs (2026-10-01)
found ids that disagree with the official text and fields the registry models oddly. Modelo 390
carries printed casilla numbers 66, 74-78, 80-83 and 114-118 on binding inputs rather than
casillas; Modelo 360 represents 146 inputs at the export position of a labelled casilla; 131's
`*-vivienda-porcentaje` and `*-vivienda-limite` hold days of activity and `deduccion-art-110-tramo`
is a bracket code; 232's `vinculada-metodo-*` name a method section 4 does not have; 369's
T36904 heading is truncated in its sidecar and union section 6 mistypes row 27; 714/720 merge the
"Situación" code and text, give C2 "% Titularidad 2" C1's heading and cut several texts at the
line wrap; 353 has "163.sixies". The names follow the official text, not the ids. Open for the
registry's owner.

### corrective-lane-reconciliation | low | committed P07 corrections pass current integration checks

Reviewed 2026-10-01 from `82b7844265`, with assertion correction `1ea2c9f348`. This checkout was clean at that starting head; no later local integration commit was present. PRs #711 and #713 remain open; no push, publication or new PR was made. This entry resolves the earlier Being fixed status for check-route-dead-end (`bddac42022`), printed-box-rule (`637bcec358`), confirm-chip (`d4956e6b3b`), and the stale verdict, duplicate diagnostics, docstrings and dock-scroll parts of p07-review-lows (`3e51374010`, `3cbe40e4f6`, `62f588960b`, `64d071c990`, `e5069b9fbc` and their subsequent integrated UX corrections). Verdict for these corrections: PASS. Fresh sequential TUI integration passed all 799 tests, exit 0 (`uv run --no-sync pytest -q -n0 -m integration src/cadrumo/entrypoints/tui`, log `C:/Users/hello/AppData/Local/Temp/.logs/test-runs/2026-10-01/20261001T122417.509876Z-pytest-78852-d5e5113c/run.log`). Two blocked-filing CLI tests and the type gate passed. After the naming changes, the owning confirmation, calculation-note and filing-gate tests passed all 36 tests (`20261001T130208.412201Z-pytest-36976-f824a605/run.log`). The confirmation test still executes the real encrypted-store edit path and proves the persisted value becomes ENTERED; its assertion now compares rendered text with StatusLine.text() inside the English settings scope.

### integrated-preview-refresh | low | 712 fresh frames cover the integrated corrective runtime

Frozen source `82b7844265` and copied authority generation `80682128474579ef10bdf92c2299305a96459bc911326a60f71bd3c0e770f3af` produced 712 frames through `dev.tui render --sequence all`, exit 0, at 80x24, 120x40, 200x50 and 80x50 in both appearances. Start and end source fingerprints agree. No frames failed or were skipped; no glyphs are missing. The 80 geometry advisories identify independently scrollable navigation, legend or source panes; none reports edge overflow or non-scrollable overflow. Reviewed the compact confirmation dialog, blocked/stale header and official grid, negative-result workbench, medium dock and annual Modelo 390. Eight scenario goldens match. The ninth, verification-reports-incomplete, differs only at notices[0].context.level: the committed confirm-chip correction changed confirm to check. The owning documentation refresh changes only that field; both its fresh sequence check and the owning how-to/verification-reports page check pass. Original captures retain their divergent provenance. Artifacts and log are under `C:/Users/hello/AppData/Local/Temp/modelo-workbench-resume-20261001/p07-snapshot/.tmp-tui-visual-inventory/runs/current` and `p07-render.log`. P07 and plan-close review remain PENDING for S62, S63 and the later planned work. The newer naming tree requires separate current captures.

### binding-name-resolution | low | optional binding text follows typed relationships and preserves unproven fields

S64 implements the approved order: binding catalogue key, owner casilla, provider casilla, unambiguous casilla at the declared record/offset, fed-box label, then unnamed. Both record ID and record type are typed coordinates; this reaches Modelo 360's page_01 relationship without guessing from names. The prepared packs contribute 2,847 distinct labels and 517 help leaves per language, with 44 grounded printed-code leaves in the box-number slot. Counts describe keys, not occurrences across revisions. Every authored leaf belongs to a declared binding and resolves in all four languages; the dedicated gate detects an orphan or missing translation. The form sweep covers every reachable published revision, and 127 owning form/help tests pass (`20261001T125705.936561Z-pytest-87392-7d81d6e0/run.log`). The locale projection, catalogue and parity checks pass (11 tests, `20261001T130303.958215Z-pytest-59452-f5425d6b/run.log`), Ruff passes and the type gate passes. No BindingDefinition field or authority publication is needed. The three Modelo 369 fichero.tipo-y-cierre fields remain visible and unnamed: typed authority data does not prove they are export-envelope constants. Earlier binding-input-registry-notes remain open for registry ownership. Visual review of the newly named tree is pending; this entry does not close the whole plan.

### naming-preview-review | low | current named forms pass their frozen visual review

Reviewed S64 at commit `3a24afb920` on 2026-10-01. A second frozen snapshot, retaining the same published authority, rendered Modelo 390, Modelo 100 and verification-reports-incomplete at 80x24 and 120x40 in both appearances: 124 frames, exit 0, all three goldens matching, no failed or skipped frames and no missing glyphs. Start and end source fingerprints both equal `aec10b6abc55519325dc2eb626980b5cafe2e970fb4f7b65beab60bc45395c77`. The 22 geometry advisories name independent scroll panes, with no edge or non-scrollable overflow. Reviewed the readable 390 first-page names and their small detail dialog, the 100 confirmation panel with separate confirm/check counts, and the incomplete 303's figures, official grid, source help and next check action. Verdict for the naming batch and its interactions: PASS. This resolves the remaining workbench lookup part of unnamed-boxes through existing schema catalogues and typed casilla relationships; the three unproven 369 envelope inputs and the registry modelling notes stay open. All 460 workbench unit tests pass on this named tree (`uv run --no-sync pytest -q -n4 -m unit src/cadrumo/entrypoints/tui/modelo/workbench/tests`, log `C:/Users/hello/AppData/Local/Temp/.logs/test-runs/2026-10-01/20261001T131821.223203Z-pytest-75608-125b2192/run.log`). The independent four-language parity check also passes (`20261001T131223.978888Z-pytest-7668-679350e3/run.log`).

The review server on port 8740 remains running and its existing page is untouched. `runs/current` holds these 124 current-source frames; `runs/corrective-82b7844265` preserves the 712-frame broad corrective capture, and `runs/handover-before-p07-resume` preserves the earlier 640-frame review. The owning `dev.tui diff` reports 548 of 712 frames changed between the handover and corrective captures, with exit 1 as its documented changed-frame result; the report is `C:/Users/hello/AppData/Local/Temp/modelo-workbench-resume-20261001/corrective-preview.diff.log`. The before/after evidence closes S28, not S50 or S30. Rate-scale and formula-values work remains queued as S62/S63; declarations and documentation convergence remain open. Artifacts for the named tree and its render log remain under `C:/Users/hello/AppData/Local/Temp/modelo-workbench-resume-20261001/naming-snapshot` and `naming-render.log`.

### S62 publication boundary reconciliation | low | Existing source owners suffice before authority publication

The companion cutover proposal is rejected before authorization or rollout. Investigation showed that the refusal came from newly added target checks, not an existing accepted transaction requirement. The accepted export-only source journal and existing generator-owned form-layout writes can converge while consumers remain on the complete prior published generation. Candidate layout regeneration and full validation remain; stale-layout and authority publication checks are not weakened. Install exports through their existing owner, regenerate forms through theirs, verify the complete tree, then publish the atomic authority descriptor. Source interruption fails closed and is repaired through these owners. The pending approval question was withdrawn in commentary. Required source installation, publication and runtime adoption still remain open for S62.

### P09 documentation verification | low | Reconciled pages and four-language links pass current builds

S57 and S58 are committed at 4124f87 and a03c505392. Forty-eight owning documentation checks and twenty-five real export/readiness CLI checks passed against the revised source. Four isolated strict user-scope HTML builds completed with zero warnings, and 24,316 rendered links/fragments passed; Chromium guide captures were inspected in es/en/ca/hu. Commands and sequence assertions were preserved; final integrated sequence/golden evidence remains at the final review gate. The guide preserves explicit PDF integrity traceability while default TUI details continue to hide identifiers.

### integrated-correction-review | medium | Fresh formula help and reachable picker controls are verified

Read-only review of 3a895bd7fe through the current integrated working tree found stale formula help cached across fresh loads, UNKNOWN-direction negative amounts rendered as positive, and initial-stage Cancel outside the 80-column picker. All three are corrected. Real encrypted-store help regressions cover apply/recalculation in both editor hosts and the late old-head fetch race; eight locale/direction cases preserve UNKNOWN signs; seventeen picker geometry cases cover both stages and Show all in four languages and both themes. Eight blocked 80x24 cases prove Help, F8, keyboard Issues and the Hungarian worded quarter remain reachable. Shared heading and stylesheet detectors pass unchanged. Verdict remains PENDING for final authority adoption, broad gates and fresh frozen captures.

### current-broad-gate-classification | low | Expanded source run exposed unsupported host checks and stale prerequisites

The expanded `pytest src -m unit -q` run returned 24945 passed and 30 failed. It overrode the canonical offline selector: twelve OS-keychain cases cannot acquire credentials in this noninteractive Windows logon session, and one OpenSSL case lacks its external executable. Six registry expectations are corrected in existing open PR711 and reflect accepted current sourcing, not authority data to restore. New workbench heading/style, source-honesty, locale wording, core-struct links, clock-seam and IVA naming findings are corrected through their owning gates; no detector was weakened. The canonical final suite remains outstanding. PR711 and PR713 were checked and remain OPEN; integration is local only, with no new PR or push.

### S62 cutover proposal disposition | low | Source authoring is repaired by existing owners before runtime publication

The proposed whole-revision companion-journal amendment is rejected and retained as decision history. It conflated mutable authoring source with the active complete registry authority. Existing export recovery remains byte-for-byte unchanged. The isolated candidate receives a generated form companion and full validation; each live export replacement is followed by the canonical form generator/check before the next target. The active runtime descriptor changes only after complete source/evidence/compiler validation. The pending approval question was withdrawn; no amendment or new publication protocol is required.

### installed-rate-authority | low | Reviewed rate exports and generated forms pass publication and adoption

S62 is installed at 536e94d4fa. Five exact-source target replacements each passed their canonical form regeneration/check, independent export check and currentness check; reviewed temporary disposition rows were retired without changing other ledger rows. Complete authority publication and all validity/runtime-load/integrity lanes passed for 58 modelos and 146 revisions. Generation bbea0e6a55b9de2ae3f4b5f00df110ac956bb604a0b8953aeac6463623595e3b serves the grounded literal percentages, including 21% and 1.75%, while zero placeholders and literals lacking a declared scale claim no rate. All six published-layout adoption cases passed. Exact installation commands, source receipts and logs are in C:/Users/hello/AppData/Local/Temp/modelo-s62-installation-sequence. Later compiler-source corrections receive a final complete publication before captures; this entry does not claim those pending gates or visual review passed.

### unrecordable-document-recovery | low | Each supported documentary refusal identifies its own ledger entry

S61 is committed at 17d35bdbc2. The existing typed deduction catalogue identifies four required authorities no production transaction writer can record: intra-EU self-assessment, customs declaration, REAGP receipt and rectification evidence. Each affected entry receives one terminal blocking finding with its native booked date, amount and actual currency, and an explicit instruction to file the declaration another way. IDs and required-authority codes remain technical. The working investment-goods register is preserved; invalid register-owned ledger rows and unknown facts retain general correction/recalculation, rather than a false attach-document promise. Sixty-three owning unit cases and eight real CLI integration cases passed, alongside narrow type/lint/format checks. The evidence includes two entries per documentary family, mixed general failures, deduplication and native foreign-currency precision. Exact checks and corrected initial fixture failures are recorded in C:/Users/hello/AppData/Local/Temp/modelo-s61-preparation/handoff.json.

### stepper-contract-reconciliation | low | Preparation belongs to declaration creation before the four workbench steps

The accepted D4 amendment dated 2026-10-02 reconciles the approved P06/P08 journey under the standing advance authorization recorded in the plan. Preparation selects a modelo and period in the declarations picker; an existing declaration then shows Fill, Calculate, Check and Record filing. The previous five-step placement is preserved as history and explicitly replaced only in this respect. Calculation, checking, export and local filing keep their guarded boundaries and one next action. Existing creation/reuse and progress evidence applies; final captures remain pending. Cross-reference placement was bounded and clipped, so its result is advisory rather than proof of complete coverage; the directly governing decisions and unchanged interface boundaries provide local coverage.

### final-review-remaining-evidence | medium | Current membership safety and frozen previews are still being completed

The rolling review re-established ledger-drift-coverage: an added in-period sale can evade a contributor-only fingerprint check. The corrective implementation now queries only registry-declared ledger source owners and retains the sealed snapshot/hash contract; its focused added-row, empty-set, held-back and exclusion checks are in flight. No passing verdict is assigned yet. S30, S50 and S56 remain open for that correction, canonical final gates, complete current authority and fresh frozen sequence/declarations review. Registry-owned modelling questions and deliberately deferred identity decisions remain explicitly separate from approved workbench obligations.

### retained-authority-membership | low | Ledger drift is evaluated within the admitted registry generation

The final correction carries the caller's PinnedAuthorityOperation through every selected ledger owner and the inner invoice IVA candidate screen. A fresh subprocess admits complete generation A, holds its actual operation and encrypted ledger, then installs generation B through the authority owner. B deliberately lacks the IVA authority: its own membership is unavailable, while the retained A operation still identifies the exact applicable transaction IDs even inside B's fact scope. No persisted ledger snapshot or hash contract changes. The developer publication test and real encrypted drift, currency, IVA and Renta cases pass together: 170 tests, exit 0, run 20261002T010819.852506Z-pytest-34712-54702cfe. This resolves the current generation-pinning gap identified during integrated review.

### final-gate-corrections | medium | Current broad TUI and CLI gates pass; remaining owning gates and captures are pending

The canonical just test-tui recipe now selects the actual import-quality detector suite in place of retired paths: 1,848 tests passed, exit 0, run 20261002T010454.929680Z-pytest-81504-e2424eed. Its separate serial selector selected zero tests (exit 5), which the recipe explicitly reports as no declared serial TUI tests; it is not additional test evidence. Eight real documentary refusal CLI cases pass after pinning, run 20261002T010738.729742Z-pytest-57012-dbacabf4. Published-layout adoption passed all six cases against the final generation bbea0e6a55b9de2ae3f4b5f00df110ac956bb604a0b8953aeac6463623595e3b; complete authority publication and validity/runtime-load/integrity gates pass. No subsequent correction changes the compiler's interpretation of registry inputs.

Current gate corrections preserve the grounded 303 rates (including 21%, 1.75% and 5.2%) and leave zero or unscaled literal placeholders unfilled. Integration tests using storage adapters moved to their outer owner; currency tests follow the current contract; dead feature-only facades were removed rather than given artificial callers. The new finite declaration locale families enrol all 31 keys and 124 ready cells. Full check-locales remains red with 19 inventoried baseline findings, including the previously accepted open reason namespaces; its current actual run is 20261002T010652.866101Z-check-locales-56640-92f6d5cd. Classification evidence is in C:/Users/hello/AppData/Local/Temp/modelo-docs-final-20261002/final-locale-findings-classification.json. Three unchanged baseline static findings are invoice_retencion.project_received_invoice_retencion, text_fold.COMBINING_MARK_UNIDATA_VERSION, and runtime-unreachable form_layout_integrity, which remains actively used by the developer compiler. The final static run also detected two new private imports in the finite-family test; the owner has corrected these and both new detector tests pass. The documentation sequence gate detected 23 stale recorded outputs, under owning review rather than masked. The final quiet unit run and the current-source frozen captures remain pending. Logs preserve initial failures and subsequent actual verdicts under C:/Users/hello/AppData/Local/Temp/modelo-s61-preparation. Integrated verdict: PENDING.

### exact-acceptance-matrix | low | Four-language filing acceptance passes at every required size and appearance

Current real encrypted-store acceptance passes all 192 cases, exit 0, run 20261002T012439.476923Z-pytest-11792-5e1eca62: es/en/ca/hu at 80x24, 120x36 and 160x48 in both themes. There are 144 workbench, actually opened sources, and expanded-help token cases for real Modelos 130 and 303; 24 editor/sources focus-return cases; and 24 native-decimal cancel/discard cases proving no staged or logged retention and unchanged stored form values/revision. The previous ordinary-size-only test coverage was insufficient for this matrix and has been extended rather than reported as passing it. The unused renewal facade is removed; seven real admission, preflight, staging and production-edit tests prove apply-time renewal still works (20261002T012752.810018Z-pytest-35908-c19072d0).

### broad-gate-final-disposition | low | Feature gates pass while actual baseline gate failures remain explicit

The quiet canonical unit run completed with 22,580 passed and one failure, exit 1: test_a_profile_switch_is_not_refused_by_a_peer_reading_the_pointer raised WinError 5 under actual Windows read/write contention. The pointer writer, atomic writer and test are unchanged from resume baseline 82b7844265. The exact real pointer read/write and permanent-refusal owning suites then passed all four tests, exit 0, run 20261002T012412.762031Z-pytest-81800-7b19a3fa; neither a timeout nor a production contract was weakened. Preserve the original broad exit 1 (20261002T010642.672625Z-pytest-89172-92660ac6), rather than claiming a wholly green unit gate. The one Typer deprecation warning is unrelated to Modelo behavior.

The two introduced private imports were corrected through bounded producer-source observation, preserving the finite vocabulary detector. The canonical import gate now passes, run 20261002T011904.807883Z-check-import-boundaries-41620-250dcb0f: all 15 graph contracts kept, 2,997 of 2,997 governed modules load, no hard finding or active architectural debt. The earlier check-code aggregate remains red for its recorded three distinct baseline reachability/unused-export findings after applying this current import recheck. Style, format, data, types, dependency declarations, secure-store writes, persistence writes and docstring references passed. The 19 baseline locale inventory findings remain visible; no new owned workbench/declarations/guide finding remains. Canonical sequence refreshes have now repaired all 23 reviewed stale recordings without changing commands, assertions or masks. The full sequence gate and current frozen visual review are still pending.

### declarations-initial-scroll | medium | Fresh portfolio captures revealed and corrected translated search-field displacement

The frozen a9439772ab P08 matrix rendered 64 frames with no failed/skipped frame, geometry report, missing glyph or source drift. Independent review of 29 images found one real medium UX issue: initial DataTable focus scrolled search partly off screen in Catalan small and entirely off screen in Hungarian small/medium. Search remained reachable with '/', but this made the initial filing view harder to use. Search and filter/sort context now sit above the content scroll; declaration rows and following content retain exactly one scroll owner. All 16 locale/size/theme geometry regressions pass, proving the complete initial bounds, attention-group focus, unchanged header bounds while scrolling to the end and '/' search focus. The full owning workspace/picker/external-details/installed-create suite passes 74 tests, exit 0, run 20261002T013428.382326Z-pytest-84724-d4f1f122. Ruff, format and canonical ty checks pass; directly expanding Basedpyright to this normally excluded module reports the same 31 diagnostics in the old frozen source, not a new geometry defect. The earlier 64-frame capture is preserved with its actual finding; fresh corrected-source captures remain required.

### documentation-sequences-current | low | All recorded CLI sequences match the current filing behavior

The owning refresh reviewed all 23 previously divergent outputs against current semantics. It changes human filing/readiness notices, adds empty typed AEAT concern arrays, corrects supplied-value attention to check, updates grounded 303 surcharge labels/help, and records the replacement ledger entry as one added and one retired contributor rather than unavailable membership. The saved calculation identity remains unchanged and the drift example still blocks filing. Commands, frame kinds, exit codes, captures, assertions and masks are unchanged. All 23 refreshes passed and the full just docs-sequences-check passes: 285 sequences across 34 pages, exit 0, cli-sequence goldens clean. The 25 non-blocking advisories (21 oversized reader frames and four unused captures) remain recorded. Exact original bytes, per-path hashes, semantic review and command results are preserved under C:/Users/hello/AppData/Local/Temp/modelo-sequences-final-20261002. Current strict localized HTML artifacts are refreshed after these changed golden inputs before final review.

### declarations-closing-review | low | Corrected four-language portfolio and picker captures pass the phase review

S56 review verdict: PASS. Frozen code cb04a1021c6a829b9b3cded1ee26c8ba0e3516bb and authority generation bbea0e6a55b9de2ae3f4b5f00df110ac956bb604a0b8953aeac6463623595e3b produce all 64 required portfolio/new-modelo/new-period/external-details frames: four languages, 80x24/120x40 and dark/light, exit 0. There are no failed/skipped frames, missing glyphs, geometry findings or source drift; all manifests share TUI fingerprint 62c91605ba3dcc5f14ccd742d1ab63828ebe235b0aa904249ab0fe144fcd571b. Independent review covers 30 PNGs, including every affected Catalan/Hungarian size/theme combination; the coordinator also inspected the corrected Spanish, Catalan and Hungarian layouts and the Catalan external-details dialog. Search and context remain visible, attention focus and one scroll owner remain, Cancel/Show all are accessible, and external filing declares its observed date without borrowing a local amount or promising unavailable linkage/receipt access. No critical/high or unresolved finding remains in the declarations phase. The original a943 capture is retained with its actual medium finding, now resolved.

Exact descriptor/source hashes and commands are in C:/Users/hello/AppData/Local/Temp/modelo-workbench-resume-20261001/p08-closing-cb04a1021c/p08-capture-evidence/receipt.json and independent-review.json. All four locale snapshots are installed through the dev/tui artifact owner under runs/p08-closing-cb04a1021c-{es,en,ca,hu}; the prior current capture is preserved as closing-before-17ea5aa02e. The review server was restarted using only just tui-review serve; review_page.html retains its original SHA256 c7219ec24e94c78491c641519f0dc7826a12d1d42b6c7f73f539f53e25bafedf. S50 and the final S30 verdict remain pending the complete workbench render/review and closing documentation artifacts.

### closing-artifact-gates | low | Current code and documentation gates have complete results and explicit baseline exceptions

The closing cb04a1021c static aggregate is complete: just check-code exits 1 with three of twelve constituent gates red solely for the three proven baseline findings already named in broad-gate-final-disposition. All nine other constituents pass, including current architecture, types and formatting; no introduced finding remains. Exact complete output: C:/Users/hello/AppData/Local/Temp/modelo-s61-preparation/code-closing-final.log. The broad unit exit 1 and its subsequent four real pointer-race/refusal passes remain separately recorded, without upgrading that full unit run to green. Full locale inventory likewise remains red for its 19 inventoried baseline issues.

After the 23 sequence goldens changed, all four strict isolated user HTML builds were rerun from current source: en/es/ca/hu all exit 0 with zero Sphinx warnings. The current artifacts pass all 24,316 local links/fragments over 60 authored pages per language and all 16 changed-output sentinels. Each of the 23 current golden hashes remains stable. Commands, exits, link and output results are in C:/Users/hello/AppData/Local/Temp/modelo-docs-closing-20261002/build-results.json, html-link-review.json and rendered-sequence-review.json. No pre-refresh HTML output is substituted for current proof. Independent code review of a9439772ab through cb04a1021c reports PASS and no critical/high finding. The complete workbench capture and its visual review remain the only outstanding plan-close evidence.

### Integrated repeating-record projection — high, S17 reopened

The fresh cb04a1021c frozen workbench capture shows two Modelo 349 operators in the summary and zero detail rows on its next page. The real calculation golden contains two persisted `detail_rows` for the `operador` binding record. The application form builder reads only `row_casilla_values`, and treats an export-record group as known whenever a revision exists. Its typed registry export record uses `repeat=binding_rows` and `binding_record=operador`; the form group selects that record. This is a real projection defect, not an empty fixture or a display filter.

S17 is reopened. The correction belongs in the generic application read model, using existing typed registry relationships and persisted values, with faithful unknown-versus-empty semantics. The running cb04a1021c 712-frame capture is retained as evidence of the defect and cannot close S50 or S30. A corrected committed snapshot, owning calculation/read-model tests, and a new integrated capture are required. The completed P08 declarations review remains valid for its unaffected declarations-summary surface.

### printed-rate integration assertion | low | published scale contract retained

The owning form integration suite exposed a stale assertion that fixed Modelo 303 box 02 had no figure. The current published export scale grounds its printed value at 4.00 percent and ratio 0.04; the test now checks that value while retaining the design-constant/informational classification. It separately proves unscaled placeholder 151 stays fixed without an invented printed rate. Five focused installed-authority scale, printed-value, unknown and placeholder cases pass (`20261002T023836.655110Z-pytest-83520-d96d9795`), as do Ruff check, format check and canonical ty for the owning test. No authority, production scale behavior or detector changed. The full owning form integration suite will be reconciled with S17's current record correction.

### repeating-record correction | low | saved rows and compact values preserved through shared owners

S17's high finding is resolved in the generic application join. The selected export record and the existing registry field-to-casilla mapping determine row ownership. Canonical persisted detail-row bindings are shared with filing replay, preserving its normalization and precedence; only CASILLA/numbered PROJECTION slots consume saved per-row casillas, so stale casilla indices cannot invent binding rows. Sparse saved binding/casilla indices, text, zero and precision survive. Explicit-empty versus omitted legacy detail channels are distinguished after real encrypted reload; unsupported projection owners remain unknown without source queries or recalculation. Numeric malformed/nonfinite tokens yield unknown cells rather than zero or a projection crash. Optional pages recognize saved records.

The related header/help defect is resolved with existing four-locale read-only/unknown wording. A further rendered-content check exposed inaccessible operator identifiers in compact summaries: the generic narrow fallback now stacks every declared labelled column/value, retains row indices and measures its full wrapped scroll height. Wide tables retain their existing layout. No modelo-specific UI, schema, stored calculation identity, locale catalogue or authority generation changed.

Applicable verification passes: 88 owning form units; 32 owning form integrations including every real registry revision; 17 record and encrypted-store cases including omitted/explicit-empty load and ghost-row exclusion; 24 real grid cases; 16 actual installed TUI cases in es/en/ca/hu at 80x24 and 120x40 in both themes, proving all saved operator identities/amounts remain reachable, no horizontal overflow and no scalar editing; six structural docstring gates within a 41-case bundle. Ruff, format, canonical ty across all nine paths and strict Basedpyright for both application owners pass. Exact native run.log/run.json paths and checker tool receipts are in `C:/Users/hello/AppData/Local/Temp/modelo-workbench-resume-20261001/s17-final-verification-receipt.json`. Root inspected the actual native receipts. Independent final source review is PASS with no critical/high finding.

The immutable cb04a1021c capture completed 712 frames, nine matching goldens, no capture failure, skip, glyph issue or fingerprint drift. Its 82 advisory geometry readings classify as 36 valid independent sibling-pane readings and 46 hidden-underlying-pane detections; no overflow or detector relaxation is involved. Twenty additional blocked/incomplete PNGs were independently reviewed with no new critical/high/medium finding; Sources counts scalar fields intentionally and row issues have a real table/source correction path. Before-fix capture is installed under `closing-cb04a1021c-before-record-fix`, with the review HTML unchanged. That capture remains REVISION REQUIRED evidence for the resolved defect; corrected frozen capture and broad gates remain S50/S30 closure work.

### record-only keyboard navigation | high | standard navigation keys did not scroll saved records

Root's integrated trace after a7a7f0360c found that the list overrides arrows, Page Up/Down and Home/End with field-cursor actions. With no selectable field, each returned without scrolling. The earlier programmatic scroll-end proof established complete rendering but not keyboard reachability. S17 was reopened. The initial a7a7f0360c frozen capture was stopped by its verified owning render process; its immutable source, partial artifacts and actual termination exit 4294967295 remain under `corrected-source-snapshot` and `corrected-sequences-execution.json`. It is not completed capture evidence. Source/authority digest before and after remains f0e92db8d8bc8e24da41631827f16448d97031da5985ee36a954c62846b88165.

### record-only keyboard correction | low | all saved values now reachable with ordinary keys

When the list has no selectable fields, arrows now scroll one line, Page Up/Down scroll a visible page with overlap, and Home/End scroll to content bounds. Field and official-grid cursor branches retain their behavior; records remain read-only. Sixteen real encrypted installed cases now use pilot key presses exclusively to traverse records in all four languages, small/medium terminals and both themes, proving forward progress, boundary clamping, every column label, all operator identities and locale-formatted amounts, unchanged calculation identity and no edit on Enter. Actual run `20261002T025555.254915Z-pytest-84332-a98de5c2` passes; unchanged owning grid 24 and cursor 7 cases also pass. Two-path Ruff, format, canonical ty and diff check pass. Root inspected the native receipts and saved checker logs in `C:/Users/hello/AppData/Local/Temp/modelo-workbench-resume-20261001/s17-keyboard-verification-receipt.json`; independent narrow review is PASS with no critical/high finding.

S17's source correction is verified again. S50/S30 still require the final committed keyboard-corrected frozen capture. The broad unit run begun before this keyboard correction will be retained with its actual scope; final canonical broad verification must use the stable corrected tree. Documentation CLI replay/goldens/build inputs are unchanged by this keyboard delta.

### closing-import-ownership | low | generated inventory and TUI test boundary corrections pass

The final just check-code run preserved its actual exit 7: eight constituents passed, the three already classified baseline constituents remained red, and the import constituent was unavailable because its finite load inventory omitted new work_form_records. The canonical import_load_probe --compile-targets owner adds exactly that module. A subsequent actual import run loaded 2,998/2,998 modules but refused ten new sibling imports, all in the shared Modelo 349 resolver test. These were introduced by S17's installed TUI acceptance cases, not baseline exceptions.

The original shared live resolver test and its non-vacuity/source-enrolment assertions remain. Synthetic invoice facts have one defining shared test helper; installed form, encrypted omitted/explicit-empty reload and keyboard cases now reside with the TUI owner and use the existing public real encrypted operator-work harness. All 22 focused cases pass, exit 0, native run 20261002T033928.158020Z-pytest-84444-5006eba1; three-path Ruff, formatting, ty and diff checks pass. Root reviewed the complete relocation and inspected actual native receipts in C:/Users/hello/AppData/Local/Temp/modelo-workbench-resume-20261001/s17-test-ownership-verification-receipt.json. No production, authority, schema or detector/ratchet behavior changed.

The final owning import driver passes on the frozen workbench candidate (5f721a1d2e plus these four exact corrected inputs), native run 20261002T034217.415427Z-check-import-boundaries-85904-2c6be814: 15/15 graph contracts kept, all 2,998 modules load, zero hard finding, unapproved edge or active debt, stable source snapshot before/after. Exact imports, input hashes and command are in closing-owned-import-receipt.json under the same C temp root. Concurrent profile UX work is deliberately outside this candidate; its files are preserved. Current frozen product captures remain applicable because the correction changes tests and tooling inventory only. Integrated review remains PENDING final capture.

### final-broad-gate-results | low | complete results retained with unrelated baseline exceptions

The keyboard-corrected canonical just test-unit passes all 22,598 tests, exit 0, native run 20261002T031326.307883Z-pytest-87180-86358022. The earlier pre-keyboard run also passed 22,598 (20261002T025105.948367Z), retained with its narrower source provenance. The historical Windows pointer-race broad failure is not erased. One unchanged Typer deprecation warning remains.

The final canonical just test-tui has 2,030 passed and one failed, exit 1, run 20261002T032508.690201Z-pytest-79916-72610c86. The original confirmation-and-apply regression passes, proving rendered StatusLine.text(), persisted ENTERED origin and unchanged confirmed figure through production preflight/apply/execution. The sole broad failure is the unrelated profile onboarding refresh (109 rather than 174 visible rows, with NoMatches for summary-renta_taxpayer). Its source/test and profile-overview producer are unchanged from handover 82b7844265 at this run. All seven owning onboarding cases plus the confirmation regression pass together, exit 0, run 20261002T033425.895102Z-pytest-82028-6971da6a; retain the full broad exit 1 rather than upgrading it. Its separate serial selection executed zero tests and is not extra evidence. Later concurrent profile UX changes belong to their own owner.

The current check-locales run 20261002T031435.942733Z-check-locales-81092-8f875580 exits 1 for the same 19 baseline inventory issues; all 29,904 required cells are ready, none missing or malformed. The 21 native records belonging to those inventoried finding kinds are byte-meaning identical to the prior classification; catalogue-only and advisory records remain in the full stream. Comparison: keyboard-locale-baseline-comparison.json under the C temp root. No introduced workbench locale issue remains. The static baseline findings remain form_layout_integrity runtime reachability, project_received_invoice_retencion and COMBINING_MARK_UNIDATA_VERSION; their detector contracts remain intact.

### superseded-publication-approval | low | late approval acknowledged after proposal withdrawal

The operator's approval reply arrived after the proposed grouped export/form-layout source transaction had already been withdrawn and recorded rejected. The existing accepted separate source owners and complete atomic authority publication had successfully finished S62 without that transaction. Root acknowledged the late reply and explained that no further publication amendment is needed for the completed approved work. The rejection remains a historical withdrawal, not a new implemented journal or change to accepted authority boundaries.

### final-frozen-workbench-capture | low | complete current product capture preserved with exact review coverage

The immutable keyboard-corrected 5f721a1d2e snapshot completes all nine selected sequence journeys and 712 frames, exit 0. Every golden matches; there are zero capture failures, skipped frames and missing-glyph frames. TUI source fingerprints start/end both ee2fbd7eac0cb13ad297ab28bd73e830f971a6851a23fbb10dc73c7148f1f43c; whole source/authority digest start/end both cdc3f115164da407d4bf516c1ac2b6052540fdbdd2d3c22b2fc3f8419efdb2d2. Commands, import roots and descriptor/database hashes are in keyboard-sequences-execution.json and keyboard-source-snapshot/frozen-receipt.json under C:/Users/hello/AppData/Local/Temp/modelo-workbench-resume-20261001. This corpus is English despite its es selector; four-language acceptance is supplied by the exact 192-case matrix and record-specific real keyboard matrix, not falsely attributed to every PNG.

Independent record review inspected 13 actual PNGs with matching manifest hashes, including all eight complete Modelo 349 record-page size/theme combinations. Summary operators2 and 8,000 EUR match both detail rows, 5,000 plus 3,000; all seven columns survive compact/wide rendering. Root additionally viewed eleven current PNGs spanning the negative 130 case, 100, 130, 303, 349 and 390. The unchanged 82 advisory geometry readings classify as 36 independent bounded sibling-pane readings and 46 hidden-underlying-pane detections; no overflow or detector relaxation is involved. Independent filing review inspected 20 actual blocked/incomplete PNGs and their text. Blocked and incomplete 303 workflows pass; the known-empty 349 guidance issue below remains open. The capture's inventory also reports 55 interfaces outside the selected sequence corpus; these are not claimed rendered. S50/S30 remain PENDING correction and affected-scenario review.

### known-empty-record-guidance | medium | zero saved rows were incorrectly explained as a filter-empty view

In the final incomplete-report Modelo 349 next-page frames, the ALL view shows Detail rows0 and five table requirements but says Nothing on this page for this filter and redirects to Declarant record; help says there are no boxes. This does not lose saved rows. page_items._record_items emits only a heading for a known-empty repeating block, losing its typed column locator and read-only source guidance; the existing screen content/help branches correctly recognize a records container. S17 is reopened for the generic zero-row container correction and real installed acceptance. The complete 712-frame capture is preserved with this actual medium finding. Required new evidence is the affected full 80-frame scenario from corrected frozen source, plus owning empty/unknown/populated and keyboard proofs. Other 632 sequence frames may be reused only with explicit unchanged-behavior/input applicability, without claiming a uniformly rerendered 712-frame fingerprint.

### known-empty-record-correction | low | source guidance and finding navigation retained at zero rows

S17 now keeps the exact typed CasillaListRecords container for every known repeating table, including zero rows, followed by the existing four-language read-only/source guidance. Unknown rows retain their distinct note. Populated tables construct the same items as before; screen content/help and column locators already support this container. No field becomes editable and no application, registry, authority, schema, calculation identity or catalogue changes.

All 38 owning real cases pass, exit 0, run 20261002T035511.642247Z-pytest-51848-f6714352: 22 existing proofs and 16 new known-empty cases in es/en/ca/hu, 80x24/120x40, dark/light. Each creates a real empty calculation and persisted verification, proves truthful count0/source guidance, no filter-empty/no-box/unknown/not-applicable claim, no edit, bounded geometry, and keyboard Issues/Enter navigation from another page to the exact country-column table. The 24 existing grids plus unknown-record column-navigation case also pass, exit 0, run 20261002T035707.515420Z-pytest-37048-77d7b3bd. Narrow Ruff, formatting, ty and diff checks pass. Root reviewed the complete two-path diff and actual native receipts in s17-known-empty-verification-receipt.json under the C temp root.

The final owning import driver passes on the exact frozen corrected candidate, run 20261002T035828.750226Z-check-import-boundaries-12772-5f02bbec: 15 contracts, 2,998 loaded modules, zero unapproved edge or debt. Both new render and import checks retain identical whole source/authority digests before/after: 57b27379d6b8286b08d04f599132389c42826d72749f5544c0fc0ea11baf38bf. Candidate inputs are rooted at cc9f4ab46a plus the exact two-path correction, excluding concurrent profile UX edits; their hashes match the owning proof. The affected complete 80-frame scenario rendered successfully with all goldens matching, no failure/skip/glyph issue or source drift. Its independent visual verdict and served installation belong to S50; S17 source correction is verified and closed.

### closing-workbench-visual-review | low | affected corrected scenario passes and phase review closes

S50 verdict: PASS. The final frozen affected scenario renders all 80 frames, exit 0, with every golden matching, no failure, skip or missing glyph. TUI fingerprint start/end is 685b4884e5b68cfe9af1a61105bed4383e9161326b075fa3cfd7bb76fdf93962; whole source/authority identity remains 57b27379d6b8286b08d04f599132389c42826d72749f5544c0fc0ea11baf38bf. The frozen source/test hashes match both actual owning proof and committed 16b6aa3e84. Exact receipt/commands are in known-empty-{render,imports}-execution.json and known-empty-source-snapshot/frozen-receipt.json under C:/Users/hello/AppData/Local/Temp/modelo-workbench-resume-20261001.

Independent visual review actually inspected 16 fresh PNGs: all eight next-page size/theme variants, two issues, two sources, two review and both small legend appearances. Root also inspected corrected small dark and medium light pages. All eight table views preserve zero detail rows and five missing requirements, show the source-owned read-only guidance, and omit the false filter-empty/next-declarant/no-box instructions. Actual real encrypted keyboard finding navigation and no-edit behavior are separately proven by the 16 new acceptance cases. The only two geometry advisories describe the focused small legend and hidden underlying list; the images show working Scroll/Esc controls, no overflow or obstructed interaction. The medium known-empty finding is resolved; no new critical, high or medium finding remains.

The final delta affects only known-empty _record_items; unknown and populated branches retain their prior behavior and scalar journeys do not call the changed arm. The full 712-frame capture is retained with its actual finding, while these 80 fresh frames replace the affected scenario's evidence. The other 632 selected sequence frames, completed corrected 64-frame four-language declarations capture, exact 192-case filing matrix, published authority adoption/export gates and applicable documentation proof remain valid for their unchanged inputs. This is scoped evidence reuse, not a claim that all 712 frames were rerendered at one final fingerprint. The owning dev/tui diff reports exactly eight changed matching next-page frames; the other 72 matching scenario frames are unchanged, while 632 outside the targeted run are marked absent by selection rather than deleted product surfaces.

The affected current run and named modelo-workbench-final-known-empty snapshot are installed through dev/tui's staged artifact owner. Complete before-fix captures remain available as closing-5f721a1d2e-before-empty-guidance and closing-cb04a1021c-before-record-fix; four corrected P08 locale snapshots remain. Review server HTTP/API respond 200 at port8740; review_page.html retains original SHA256 c7219ec24e94c78491c641519f0dc7826a12d1d42b6c7f73f539f53e25bafedf. Another profile UX owner continues in its own scope; its source, catalogues, capture harness and named review work are preserved.

## Recommendations

- The accepted operator-layer decision D6 explicitly defers recording an override reason and the displaced source value; sources-hub-reason remains that separate decision question.
- The accepted D4 amendment covers the four workbench steps, with preparation in the declarations picker; D5's docked editing and official grids are implemented. No follow-on workbench-shape decision is outstanding.
- The reproduced negative-yield omission premise was withdrawn; a future blank-by-rule origin needs a grounded case before any additional implementation.
- Registry owners retain the grounded questions recorded in informative-totals, window-opens, modelo-100-direction, transport-tokens, binding-input-registry-notes and the unproven Modelo 369 envelope constants. No label is used as evidence of a constant's export-envelope role.
- The unused official_page and renew_edit_baseline facades have been removed. The live apply path continues to renew through its existing required renewal operation; all seven owning admission/preflight/staging/production-edit cases pass. Final current-source visual review determines closure.
