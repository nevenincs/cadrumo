---
tags:
  - '#audit'
  - '#modelo-editor-workbench'
date: '2026-09-30'
modified: '2026-09-30'
body_schema: 'body-v2'
body_hash: 'sha256:60db05f74c2968b7d0e1a03aa33aff4a8f97c15d42854942fb294f301ec5dc05'
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

## Recommendations

- sources-hub-reason: a follow-on ADR decides whether the operator layer records an override
  reason and the displaced source value, and how that participates in revision identity.
- workbench-shape: a follow-on ADR decides whether D4's five-step stepper, official grids and
  technical drawer, and D5's inline editing of simple types, stand or are amended.
- blank-by-rule: a follow-on ADR decides the closed origin for a box left blank by rule.
- transport-tokens: define one read-back of enumerated binding values shared by the form and
  presentation.
- dead-code: wire `renew_edit_baseline` into review-time renewal or delete it with `official_page`.
