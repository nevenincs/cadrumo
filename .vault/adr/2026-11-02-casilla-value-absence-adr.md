---
tags:
  - '#adr'
  - '#casilla-value-absence'
date: '2026-11-02'
modified: '2026-11-02'
body_schema: 'body-v2'
body_hash: 'sha256:6deab17ce63393d607a0153b947a36a1374f1cf58e024ec6f25eb5d545dbae12'
related:
  - "[[2026-11-02-casilla-value-absence-research]]"
  - "[[2026-06-19-silent-zero-base-aggregation-adr]]"
  - "[[2026-08-07-silent-zero-regression-screen-adr]]"
  - "[[2026-06-30-modelo-verify-nonzero-guards-adr]]"
  - "[[2026-08-10-casilla-schema-read-model-adr]]"
  - "[[2026-09-30-modelo-editor-workbench-adr]]"
  - "[[2026-11-01-export-parity-binding-capability-grade-adr]]"
  - "[[2026-11-01-export-parity-income-imputation-criterion-adr]]"
  - "[[2026-11-01-export-parity-suffered-withholding-schemas-adr]]"
  - "[[2026-11-01-export-parity-observation-filing-kind-adr]]"
---

# `casilla-value-absence` adr: `One closed vocabulary for a casilla value and its absence` | (**status:** `proposed`)

Nothing here applies until the operator accepts it. The proposed edits to accepted records stay unapplied until then.

## Problem Statement

A draft can show `01 = 0` beside a blocker and "Box 06: the zero stands" beside an unresolved note. `2026-11-02-casilla-value-absence-research` traces this to three causes: the engine seeds a real zero for every unentered manual box; "proven zero" means three incompatible things across accepted records; and each surface spells absence its own way with no owner. Each new feature has re-decided the point locally. This record rules once for the whole product.

## Considerations

- A file cannot carry "unresolved", and the fill for an empty numeric slot is set per design: zeros in DR190 and DR347, the only stated fill in DR130 and DR303 (inference), spaces and "nunca con ceros" in DR369 (research, finding 6).
- Official instructions make some boxes zero on a condition (130 casillas 04, 12, 18) and some blank on a condition (303 casilla 70), and a zero result leads to "Negativa" (research, finding 7). No blanket official default of zero was found.
- How a draft shows an untouched box is a product choice: no official text found regulates it. AEAT guidance shows awaited amounts empty and treats `0,00` as a value (research, finding 8). How AEAT's authenticated forms open was not observed.
- Blank also means "the correct answer" in AEAT's vocabulary, so a bare blank is ambiguous.
- `.claude/rules/07-aggregation-and-calculation-services.md` and `.claude/rules/09-filing-and-live-state.md` already require these states to stay distinct and forbid padding from supplying a required fact, but name no owner or gate.

## Considered options

- **Keep a zero with a blocker note.** Smallest change, but a figure is read before its note, and it is what the operator rejected.
- **Bare blank for every no-figure state.** Matches the leaning. Rejected alone: it cannot separate "missing, blocks" from "permitted, correct".
- **Words or a dash in the value cell.** Keeps one column and states the reason, but reads as content. Kept only as a fallback where a layout has no state column.
- **Blank value cell with a state word beside it, and a typed provenance rule for every zero.** Chosen.
- **A `DEFAULTED_ZERO` state for legally implied zeros.** Rejected: every official zero found is a rule on a condition, so it is a formula or a conditioned proof, and a named default would invite unconditioned zeros.
- **Treat an empty ledger window as proven zero, as today.** Rejected: no ledger-completeness concept exists, so no rows proves nothing about the filer's activity.

## Constraints

Obligations:

1. **Vocabulary.** `CasillaValueState` is the only classification of a casilla's value, closed at the nine members below, defined once in `src/cadrumo/core/casilla_value_absence.py`. Form origins, report states and notes project from it. No surface or feature adds a state or derives its own.
2. **A zero needs provenance.** A casilla displays or stores a zero only in a figure state, with the evidence that state requires. No zero exists by default.
3. **No placeholder.** A no-figure state has no numeric value and no stored observation value.
4. **Blank is never alone.** A no-figure state shows an empty value cell and its state word next to it, in the accessible name too. The em dash, `·`, `…`, "sin dato" and "n/a" leave the value cell.
5. **Screen and file are separate.** Screen display is this record's choice. File bytes follow the selected official design through the registry layout. A blank on screen reaches a file as the design's fill only for a state that allows it; padding never supplies a required fact.
6. **Propagation.** The formula rule below is uniform across input kinds and modelos, with no modelo-name branch.
7. **Replay.** Revisions recorded as filed keep their history. Unfiled revisions recalculate through the screen stamp of `2026-11-01-export-parity-binding-capability-grade-adr`, by raising its contract version. Nothing rewrites stored revisions.

Scope: casillas and scalar bindings of every modelo on every surface; row-channel values follow the same states per row. Out of scope: taxpayer profile facts other than where they feed a box, and live submission, which stays refused.

### The ruling

| State | Meaning and required evidence | Typed form | Screen | Downstream formula | Verify, export, file |
| --- | --- | --- | --- | --- | --- |
| `ENTERED` | The filer typed a value, zero included | figure + entered provenance | figure, `0,00 €` | value | Normal; file value |
| `SOURCED` | A source returned a value from rows or a filed observation; rows summing to zero included | figure + source provenance | figure | value | Normal; file value |
| `COMPUTED` | A formula over operands with at least one figure and none propagating; "04 is zero if 03 is negative" lands here | figure + formula provenance | figure | value | Normal; file value |
| `PROVEN_ZERO` | Zero on a named basis: `legal_condition` (registry-cited rule whose condition holds on typed evidence), `attested_absence` (recorded operator statement with note), or `declared_absent` (a positive profile answer) | zero + basis + citation | `0,00 €`, basis in help | value | Normal; file value |
| `NOT_APPLICABLE` | Typed evidence, not silence, shows the box does not arise | no figure + reason | blank, "No aplica" | neutral operand | Passes; design's fill |
| `PERMITTED_BLANK` | The registry declares the box may stay empty and nothing was supplied, or official text directs it blank | no figure | blank, "Opcional" | neutral operand | Passes; design's fill |
| `MISSING` | Applicable, nothing supplied, and the filer or an import can supply it; includes an empty source window | no figure + what is awaited | blank, "Falta" plus remedy | propagates | Refuses verify, export, filing |
| `UNRESOLVED` | A source or formula ran and settled nothing, applicability is unknown, or the calculation has not run | no figure + reason | blank, "Sin resolver" or "Sin calcular" | propagates | Refuses verify, export, filing |
| `DEFERRED` | No producer owns this value in this revision | no figure + owner and condition | blank, "No disponible aún" | propagates | Refuses verify, export and filing when it reaches a printed box |

Advisory is not a state: a capped value keeps its figure state, and its cap blocks as `2026-11-01-export-parity-binding-capability-grade-adr` rules.

**Surfaces.** Desktop and TUI follow the table. CLI text prints the key, an empty value and the state; JSON keeps figures in `casilla_values` and adds a state entry for every printed box, so omission alone never signals absence. MCP passes those documents unchanged and adds no mapping. PDF and report show blank plus the word in a state column; a layout with no room for one may print the word in place of the figure. Workbook shows an empty cell with the state word and keeps its "Falta dato" against "Cero indicado" distinction. Each surface renders the application's state and never classifies on its own.

**Formulas.** A propagating operand leaves the target with no figure and state `UNRESOLVED`, naming the operand. Neutral operands read as zero only through one named ground in `AbsentCasillaReading`, replacing `UNSUPPLIED_INPUT`. A formula whose operands are all neutral stays no-figure and inherits `NOT_APPLICABLE` or `PERMITTED_BLANK`, so `09` does not show a `0,00` computed from nothing (open question 3). Advisory predicates keep reading absent operands under their existing grounds and never establish a figure.

**Form-level legal zeros.** A zero a form implies shows as a zero only with its condition proved:

- A rule the formula expresses is `COMPUTED`: 130 casillas 04 and 12.
- A rule on a typed condition is `PROVEN_ZERO` with `legal_condition`: 130 casilla 18 on an admitted original under `2026-11-01-export-parity-observation-filing-kind-adr`.
- An unknown condition stays `UNRESOLVED`, never zero.
- Official text directing blank is `PERMITTED_BLANK`: 303 casilla 70.

**Filing statements.** A marking that asserts a zero, such as 130 "Negativa" or 303 type `N`, derives only from a figure state. "Sin actividad" and "resultado cero" stay distinct facts.

**Empty source window.** A source that ran over no row and no accruing document yields `MISSING` with reason `no_records_in_window`, and `attested_absence` clears it. Rows present yield `SOURCED`, even at zero. Open question 1 can change the blocking effect, not the display.

**Locale.** One key per state, `workspace.modelo.value_state.<state>`, plus one remedy key per reason, authored through `dev.locales` in all four languages, with informal singular address in es, ca and hu. State tokens stay untranslated in transport. Proposed words, pending the catalogue pass and native review for ca and hu:

| State | es | ca | en | hu |
| --- | --- | --- | --- | --- |
| `NOT_APPLICABLE` | No aplica | No s'aplica | Does not apply | Nem alkalmazandó |
| `PERMITTED_BLANK` | Opcional | Opcional | Optional | Nem kötelező |
| `MISSING` | Falta | Falta | Missing | Hiányzik |
| `UNRESOLVED` | Sin resolver | Sense resoldre | Unresolved | Nincs megállapítva |
| `UNRESOLVED`, not yet calculated | Sin calcular | Sense calcular | Not calculated | Nincs kiszámítva |
| `DEFERRED` | No disponible aún | Encara no disponible | Not available yet | Még nem érhető el |

Retired wording: "the zero stands" in all four languages, "Optional, left at 0" (`workspace.modelo.origin_held_zero`), and "proven" in operator text for anything but a named basis. Replacement note where rows exist and carry no retención: "Box {box}: no entry in the period carries a retención, so its period is not in doubt." It names only the cap question and shows at the box it concerns.

### Affected prior rulings

Amends, with wording proposed under Consequences: `2026-11-01-export-parity-binding-capability-grade-adr`, `2026-08-07-silent-zero-regression-screen-adr`, `2026-11-01-export-parity-observation-filing-kind-adr`, `2026-11-01-export-parity-suffered-withholding-schemas-adr`, and the rules files. Consistent and unchanged in substance: `2026-11-01-export-parity-income-imputation-criterion-adr`, `2026-06-19-silent-zero-base-aggregation-adr`, `2026-06-30-modelo-verify-nonzero-guards-adr` (guards stay advisory), `2026-08-10-casilla-schema-read-model-adr` and `2026-09-30-modelo-editor-workbench-adr` (the row gains the state; origin layers stay) and `2026-06-01-metastate-zero-tolerance-adr` (the gate below carries no migration allowlist). Supersedes none. `2026-09-30-modelo-editor-workbench-casilla-row-research` section 2.3 is research and is overtaken here.

## Implementation

We will add `CasillaValueState`, stop materialising a zero for any no-figure state, make formulas treat every input kind by that state, and project one display across every surface, enforced by the gate below. A plan sequences this, since it spans registry, calculation and frontend work across sessions.

Affected surfaces (shapes are hypotheses; the table binds):

- Core: `src/cadrumo/core/casilla_value_absence.py`, `core/aggregation.py` (`BindingValueOutcome.PROVEN_ZERO` renamed to say only "no bearing row").
- Engine: `domain/calculations/registry/formula_initial_values.py`, `formula_runtime.py`, `formula_runtime_ops.py`, `bindings.py`. Registry: a declared `blank_policy` on casillas for `PERMITTED_BLANK`, read beside `required` (open question 2).
- Resolvers: `application/aggregation/renta_imputation.py`, `domain/calculations/registry/ledger_renta_income_bindings.py`, `application/aggregation/source_mesh.py`; an attestation operation reusing the pattern of `2026-11-01-export-parity-suffered-withholding-schemas-adr` section 5.
- Application: `application/modelo/work_form_field_state.py`, `work_form_field_projection.py`, `work_form_wording.py`, `value_presentation.py`, `calculation_notes.py`, `calculation_note_gate.py`, `advisory_binding_value.py`, `declaration_summary.py`, `calculation_report.py`, `calculation_summary_presentation.py`, `_calculation_modelo_adjustments.py` (its M390 silent-zero refusal becomes the general rule), `application/storage/calc_sheets/`.
- Export: `application/filing/` and `fixed_width_codec.py` (the required refusal becomes reachable), `_export_xml_dictionary_modelo100.py` (placeholder handling retires), declaration-type derivation.
- Frontends: `native/desktop/frontend/src/components/modelo/form/ValueCell.tsx`, `GridBlock.tsx`, `RecordsBlock.tsx`; `entrypoints/tui/modelo/workbench/casilla_list_values.py`; `entrypoints/cli/operation_modelo_calculation.py`, `modelo_results.py`; `native/desktop/frontend/scripts/modelo_fixtures.py` and regenerated fixtures.
- Locales: all four catalogues through `dev.locales`.

Defects found, with evidence in the research:

- D1 `formula_initial_values.py:541`: an unentered manual box stores a zero, identical in the value map to an entered zero (probe).
- D2 `work_form_field_state.py:136-145` against `work_form_wording.py:149-153`: same name, opposite answer on zero; origin `OPTIONAL_EMPTY` shows a `0`.
- D3 `renta_imputation.py:67-71`, `ledger_renta_income_bindings.py:671-694`: an empty ledger is `PROVEN_ZERO`.
- D4 `advisory_binding_value.py:72-101` and the four locale sentences: a cap statement reads as a verdict.
- D5 `calculation_notes.py:301-302` against `calculation_note_gate.py:64-83`: `unresolved_binding` with no box reads "check" and withholds filing, and the module header at `calculation_notes.py:22-26` states the opposite of the gate.
- D6 `formula_initial_values.py:525-526`: an unanswered profile yes/no reads as not applicable.
- D7 `formula_initial_values.py:545-546`, `:562-563`: a relation slot with no filing is flagged absent-by-design and seeded zero, against `2026-08-07-silent-zero-regression-screen-adr`; end-to-end effect not traced.
- D8 `formula_runtime_ops.py:161-165`: unparsable text reads as zero.
- D9 `core/casilla_value_absence.py:49-54`: `OMITTED_BOX_DECLARES_ZERO` states as law what is only a byte-level inference.
- D10 Absence has six spellings across surfaces, and CLI and JSON omit state entirely.
- D11 `fixed_width_codec.py:589-591`: its promise that an omitted mandatory figure cannot reach the wire does not hold for manual boxes given D1; verification's required check is the only stop.
- D12 `_export_xml_dictionary_modelo100.py:79-91`: the exporter works around D1's placeholders.

**Conformance gate.** It has no allowlist of unconverted items:

- Type: `CasillaObservation` refuses a value without a figure state, and a nonzero value under `PROVEN_ZERO`, so a placeholder cannot be constructed.
- Totality at import, in the style of `_require_total_levels` in `calculation_notes.py`: every `ModeloFormOrigin` and report state maps to one state, and every state has its locale key in all four languages.
- Source scan under `dev/quality/tests/`: a zero default on a casilla-keyed read (`.get(id, ZERO)`, `or Decimal(0)` and similar) outside `AbsentCasillaReading` fails, with a planted-defect fixture proving the scan fires.
- Engine, through the real calculator with hand-derived oracles: for Modelo 130 and representative 303 and 100 revisions, every stored zero has provenance, a propagating operand leaves its dependent chain with no figure, and an entered zero differs from an unentered box. Reseeding a zero at `formula_initial_values.py` must fail this.
- Surfaces: one state-table test per frontend drives a fixture of every state and asserts an empty value cell plus the word in all four languages, and no `—`, `·`, `…` or retired sentence in a value cell or catalogue.
- Export: a required layout field in any no-figure state refuses; `NOT_APPLICABLE` and `PERMITTED_BLANK` render the design's fill on DR130 and DR369 (zeros and spaces); `Negativa` cannot derive from a no-figure box. Isolated fixtures prove each.

## Rationale

The blank leaning survives, within limits the evidence sets. Blank fits how AEAT guidance shows awaited amounts, and no official text found forbids it on a draft. But blank is also an official answer, some boxes are officially zero, and files have their own rules, so blank is how the value cell displays a state, not the state itself. Typing the state and requiring provenance for a zero removes the ambiguity at its source; another note beside a zero would not. Named bases adopt the strictest accepted record, section 5 of `2026-11-01-export-parity-suffered-withholding-schemas-adr`. One owner and a constructor-level refusal make the rule mechanical. Empty-window `MISSING` costs a confirmation, but a zero from no evidence is the silent under-declaration the project forbids.

## Consequences

- Gains: a figure on screen always has a reason, a blank always says why, and screen, report, workbook and file cannot disagree on state.
- Costs: broad change across engine, recalculated drafts, goldens, fixtures and locales; zero-activity filers confirm once per declaration, subject to question 1; JSON gains a contract field.
- Pitfalls: `PERMITTED_BLANK` too wide recreates silent under-declaration, and too narrow blocks Modelo 100's roughly 1,979 manual boxes, hence question 2. Attestation can become a reflex click, so it records an operator statement, never third-party evidence.
- Reconsider if an attended session shows AEAT's forms open with visible zeros and that matters to filers, if an official text states a default for untouched boxes, or if a ledger-completeness concept appears that could replace attestation.

### Proposed wording for accepted records (not applied)

- `2026-11-01-export-parity-binding-capability-grade-adr`, Zero values, after the sentence defining a proven zero: "This settles only the cap. Under `2026-11-02-casilla-value-absence-adr` the outcome is named no-bearing-row: with rows present the value is `SOURCED`; with no rows at all the box is `MISSING` with reason `no_records_in_window`, whatever the cap says."
- `2026-08-07-silent-zero-regression-screen-adr`, Rationale, after the three-state sentence: "This model covers binding resolution. `2026-11-02-casilla-value-absence-adr` owns the value state of every casilla, including manual boxes, and a no-prior-filing slot holds no zero."
- `2026-11-01-export-parity-observation-filing-kind-adr`, Proven-zero rule, appended: "This is the `legal_condition` basis of `2026-11-02-casilla-value-absence-adr`."
- `2026-11-01-export-parity-suffered-withholding-schemas-adr`, section 5, Proven zero, appended: "These are the `SOURCED` state and the `attested_absence` and `declared_absent` bases of `2026-11-02-casilla-value-absence-adr`."
- `.vaultspec/rules` sources of `07-aggregation-and-calculation-services` and `09-filing-and-live-state`, after the absent-and-zero sentences: "`CasillaValueState` in `core/casilla_value_absence.py` is the closed vocabulary; a zero needs a figure state." Applied through `vaultspec-core sync`, only on request.

### Open questions for the operator

1. **Does an empty source window block?** Recommended: yes, `MISSING` until one attestation per declaration. The alternative shows blank with a warning and lets the filer proceed, so a filer who forgot to import can reach a `Negativa`. This changes every zero-activity filing.
2. **Unentered optional manual boxes with unknown applicability, such as 130 casilla 08 agrarian income.** Recommended: registry-declared `blank_policy`, permitted for deductions and elections; income-bearing boxes `MISSING` where a profile fact can decide, and `PERMITTED_BLANK` with an advisory where none can. Classifying Modelo 100's manual boxes is real authoring work.
3. **All-neutral formula targets, such as 09 when 08 is blank.** Recommended: blank, with the design's fill in the file. No official text decides it.
4. **Attended observation.** A PRE130 or Renta WEB session could confirm how AEAT opens untouched boxes. It would inform the look, not the typed rule, and is not required to proceed.

Unsettled by evidence rather than by choice: whether a DR130 or DR303 empty slot is officially zero or merely padded. The ruling does not depend on it, since both are the same bytes. Also unverified: the discrepancy between 130 casilla 02 `required = true` in the registry and `required: false` in the fixture, and whether any M369 field reaches its design fill from a seeded zero. Deferred boxes refuse at export only where they reach a printed box; today's export behaviour for them may differ and needs checking in the plan.
