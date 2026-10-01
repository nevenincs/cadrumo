---
tags:
  - '#audit'
  - '#modelo-editor-workbench'
date: '2026-09-30'
modified: '2026-10-01'
body_schema: 'body-v2'
body_hash: 'sha256:6957080d13cc3fa488319a3d3c40dc52495f001d213ad17f9bc2c7c512f0c7f4'
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

## Recommendations

- sources-hub-reason: a follow-on ADR decides whether the operator layer records an override
  reason and the displaced source value, and how that participates in revision identity.
- workbench-shape: a follow-on ADR decides whether D4's five-step stepper, official grids and
  technical drawer, and D5's inline editing of simple types, stand or are amended.
- blank-by-rule: a follow-on ADR decides the closed origin for a box left blank by rule.
- transport-tokens: define one read-back of enumerated binding values shared by the form and
  presentation.
- dead-code: wire `renew_edit_baseline` into review-time renewal or delete it with `official_page`.
