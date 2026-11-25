---
tags:
  - '#research'
  - '#casilla-value-absence'
date: '2026-11-02'
modified: '2026-11-02'
body_schema: 'body-v2'
body_hash: 'sha256:cde3636f7bfb42dc4637bc7c05c16f255a3dc7620d17c481708b8527866a3cd6'
related:
  - "[[2026-06-19-silent-zero-base-aggregation-adr]]"
  - "[[2026-08-07-silent-zero-regression-screen-adr]]"
  - "[[2026-09-15-runtime-verification-lane03-r05-absence-versus-zero-audit]]"
  - "[[2026-09-30-modelo-editor-workbench-casilla-row-research]]"
---

# `casilla-value-absence` research: `Casilla value absence`

How should Cadrumo represent and display a casilla with no established value, and what does official evidence constrain? Every draft a filer reads and every zero a file carries depends on the answer, and the point keeps being reopened. The code already keeps a real absence for bound and computed boxes, but seeds a stored zero for every unentered manual box and labels a zero over an empty ledger "proven". Accepted records use "proven zero" in three incompatible senses, which is the root of the ambiguity. AEAT regulates the file and some individual boxes; no official text found regulates how a draft shows an untouched box. Blank is admissible on screen, but a bare blank collides with AEAT's own use of blank as a valid answer.

## Findings

### 1. The engine treats "no value" in two opposite ways, depending only on the box's input kind

A bound box whose binding is unresolved, and any formula reading it, is omitted. An unentered manual box is seeded with a real zero, and every formula reading it computes.

- Omission: `src/cadrumo/domain/calculations/registry/formula_initial_values.py:458-465`, `formula_runtime.py:149-153`, `:770-772`, `formula_runtime_ops.py:109`.
- Seeded zero: `formula_initial_values.py:541`, under the ground `AbsentCasillaReading.UNSUPPLIED_INPUT` (`src/cadrumo/core/casilla_value_absence.py:25-31`). The result is stored as an ordinary observation.
- Narrow probe on 2026-11-02 through the real calculator, Modelo 130 `2019-y-siguientes`, 2026 1T, published authority under `.authority/`, every binding unresolved and no inputs: `01, 02, 03, 04, 07, 12, 13, 14, 15, 17, 19` absent; `05, 06, 08, 10, 16, 18` = `0`; `09, 11` = `0.00`. So `09` (2 % of `08`) is a computed zero resting on nothing. Repeating with `16 = 0` entered gives an identical value map, so the values alone cannot tell an entered zero from an unentered one.
- Other zero seeds: an unanswered bound profile yes/no reads `ZERO` flagged absent-by-design (`formula_initial_values.py:525-526`), so an unknown answer reads as not applicable. A structurally absent observation-backed slot reads `ZERO` flagged the same way (`:545-546`), and any unresolved `relation_prefill` slot qualifies (`:562-563`); whether callers keep it out of arithmetic was not traced end to end. Blank or unparsable text reads `ZERO` (`formula_runtime_ops.py:161-165`).
- The leak is acknowledged downstream: "Calculated drafts carry zero-valued placeholders" (`src/cadrumo/application/filing/_export_xml_dictionary_modelo100.py:82`).

### 2. The state inventory is large, unowned and split across several vocabularies

| Layer | States | Locator |
| --- | --- | --- |
| Read grounds | six named grounds for reading absent as zero | `core/casilla_value_absence.py:22-69` |
| Formula result | value, no observation, unresolved outcome with reason | `domain/calculations/registry/formula_runtime.py:183`, `:747-772` |
| Observation flag | `absent_by_design` beside a zero value | `domain/calculations/registry/bindings.py:161` |
| Resolver outcome | `PROVEN_ZERO`, `FROM_BEARING_ROWS`; `ComplementariaOnlySourceOutcome.PROVEN_ZERO` | `core/aggregation.py:726-739`; `domain/modelos/filing_kind_evidence.py:331-366` |
| Review row | `ModeloValueKind.EMPTY` and others; report `VALUE`, `ABSENT`, `NOT_APPLICABLE` | `application/modelo/_work_review_assembly.py:288-316`; `calculation_report.py:438-444` |
| Form origin | `NOT_APPLICABLE`, `CALCULATED`, `NOT_CALCULATED_YET`, `CALCULATION_FAILED`, `IMPORTED`, `NOT_IMPORTED_YET`, `NEEDS_INPUT`, `CLEARED`, `ENTERED`, `OPTIONAL_EMPTY`, `DEFAULT_TO_CONFIRM`, `OVERRIDES_SOURCE`, `INFORMATIONAL` | `application/modelo/work_form_field_state.py:60-133` |
| Notes | `UNWORKED_BOX_REASONS` and others | `application/modelo/calculation_notes.py:118-202` |

Two same-named functions disagree: `work_form_field_state.py:136-145` `_holds_nothing` counts a zero amount as nothing, so an unentered zero becomes `OPTIONAL_EMPTY`; `work_form_wording.py:149-153` `holds_nothing` says "never a zero amount". The `0` then displays with the words "Optional, left at 0" (`work_form_wording.py:142-145`, `locales/en/common.yml:9914`), contradicting "Absence is never a figure" (`value_presentation.py:15-17`).

### 3. Each surface spells absence differently, and none shows a plain blank with its reason

| Surface | No value | Zero | Locator |
| --- | --- | --- | --- |
| Desktop | em dash | `0,00 €` | `native/desktop/frontend/src/components/modelo/form/ValueCell.tsx:59`, `GridBlock.tsx:41`, `RecordsBlock.tsx:74` |
| TUI | "sin dato", `·`, `…` by origin | figure | `src/cadrumo/entrypoints/tui/modelo/workbench/casilla_list_values.py:91-92`, `:181-182` |
| CLI text and JSON | line or key omitted, no state | figure | `entrypoints/cli/operation_modelo_calculation.py:83-84`, `modelo_results.py:1059` |
| PDF summary | "sin dato", "n/a" | figure | `application/modelo/calculation_summary_presentation.py:252-256` |
| Report CSV | empty value plus `value_state` | figure | `calculation_report_document.py:218-219` |
| Workbook | empty cell; "Sin dato"; "Falta dato" against "Cero indicado" | figure | `application/storage/calc_sheets/engine.py:258`, `form_cell_builder.py:206-207`, `form_builder.py:71` |
| MCP | no own projection; passes operation documents | as source | `src/cadrumo_mcp/mcp/admitted_operations.py` |
| Fixed-width file | required refuses, optional takes the design fill | zero-padded | `domain/calculations/registry/fixed_width_codec.py:577-596`, `:599-619` |
| XML file | absent optional element omitted | as value | `application/filing/export_parity.py:439-441` |

The file refusal is largely unreachable for manual boxes: finding 1's zero arrives as a value, so only verification's required-casilla check stands between an omitted manual figure and the wire. The workbook alone already separates blank from indicated zero. The desktop, CLI and MCP locators came from a read-only sweep; `ValueCell.tsx`, `casilla_list_values.py`, `form_builder.py` and the codec were re-read directly. The PDF writer past its value text was not opened.

### 4. "The zero stands" is about one binding's grade cap, printed beside a statement about other boxes

The sentence is `application.modelo.calc_diagnostic_fact.advisory_value_proven_zero` (`src/cadrumo/locales/en/application.yml:1518-1519`; es `:1603`, ca `:1601`, hu `:1566`), chosen at `application/modelo/advisory_binding_value.py:72-101`. It fires when `ledger_renta_withholding_value_outcomes` finds no retención-bearing row (`domain/calculations/registry/ledger_renta_income_bindings.py:671-694`). An empty ledger qualifies. Nothing relates it to the rest of the revision, so the fixture `native/desktop/frontend/src/dev/fixtures/modelo/modelo-130-1T-es.json` shows together: `01 = 0 imported`, `02 = 0 imported`, `06 = 0 optional_empty` with the note, boxes `13, 14, 15, 17, 19` as `calculation_failed`, and an `unresolved_binding` note at attention `check` with `withholds_filing: true`. The note on 06 and the blocker concern different things, but "stands" reads as a verdict on the declaration.

That blocker exposes a second disagreement: `calculation_notes.py:22-26` and `:301-302` treat an unresolved binding with no printed box as only worth checking, while `calculation_note_gate.py:64-83` refuses it wherever it points. The note speaks as a check and acts as a block.

`01 = 0` itself comes from a ledger sum over no rows; `application/aggregation/renta_imputation.py:67-71` calls that `PROVEN_ZERO` when no row and no accruing invoice exists. A targeted grep found no ledger-completeness or period-closure concept in source (`application/ledger/closure_findings.py` concerns invoice arithmetic), so an empty window proves only that the records are empty.

### 5. Accepted records disagree on what proves a zero

- `2026-11-01-export-parity-binding-capability-grade-adr`, Zero values: proven zero is a window with no bearing row. An absence of evidence suffices.
- `2026-11-01-export-parity-suffered-withholding-schemas-adr`, section 5: missing never resolves to zero; proven zero needs records summing to zero, an attestation with a note, or a class positively declared absent.
- `2026-11-01-export-parity-observation-filing-kind-adr`, Proven-zero rule: an official rule plus an admitted evidence basis.
- `2026-08-07-silent-zero-regression-screen-adr` declares one three-state model (resolved, absent-by-design, missing-error) and holds a no-prior-filing slot to be a blank the operator fills, not an engine zero, though the code flags that slot and seeds zero. It does not reach manual boxes.
- `2026-06-19-silent-zero-base-aggregation-adr` forbids a regulated base resolving silently to zero, scoped to aggregation gaps. `2026-06-30-modelo-verify-nonzero-guards-adr` adds advisory nonzero guards and never asks how a zero arose.
- `2026-08-10-casilla-schema-read-model-adr` keeps origin layers apart and rules no display. `2026-09-30-modelo-editor-workbench-casilla-row-research` section 2.3 labels any engine zero "proven zero" and lists seven absences. `2026-06-01-metastate-zero-tolerance-adr` concerns migration lists, not values, and bears only on the shape of a gate.
- `.claude/rules/07-aggregation-and-calculation-services.md` lists states to keep distinct and `.claude/rules/09-filing-and-live-state.md` requires missing, required blank, permitted blank and zero to differ, with padding never supplying a required fact. Neither names an owner, a display or a provenance test.
- `2026-09-15-runtime-verification-lane03-r05-absence-versus-zero-audit` found absence distinguishable only by key membership: "A consumer that reads the mapping with a zero default would erase the distinction." Finding 1 shows the calculation doing this for manual boxes.

No record says what a zero must rest on, and none covers an unentered manual box or the screen.

### 6. Official sources regulate the file by design, and the designs differ

Stated by the source, under `src/cadrumo/_data/corpus/aeat_official/disenos_registro/`:

- DR130 and DR303: numeric data align right "rellenando con ceros por la izquierda" (`modelo_130/files/01-130-orden-hap-258-2015-ejercicios-2019-y-siguientes-actualizado-marzo-2019-176-kb-xls.xls.extracted.md:77-78`; `modelo_303/files/01-303-ejercicio-2026-y-siguientes-actualizado-28-01-26-378-kb-xlsx.xlsx.extracted.md:142-143`). Neither says what an empty field holds.
- DR190 and DR347: "Si no lo tuvieran, los campos numéricos se rellenarán a ceros" (`modelo_190/files/01-190-orden-eha-3127-2009-de-10-de-noviembre-ac.pdf.extracted.md:55-57`; `modelo_347/files/01-347-ejercicio-2025-y-siguientes-modificados-p.pdf.extracted.md:26-28`).
- DR369: "En particular en los campo numéricos (Num) sin información se rellenarán también con espacios en blanco y nunca con ceros" (`modelo_369/files/01-369-regimenes-especiales-aplicables-a-los-ser.xlsx.extracted.md:36`). The registry already carries this as `absent_fill` (`domain/calculations/registry/schema_exports.py:587-593`).
- Modelo 100 XML: 7087 of 7259 schema elements are `minOccurs="0"` (`modelo_100/files/`, the 2025 XSD), so absence is omission there.

Inference: on DR130 and DR303 an optional empty numeric slot and a declared zero are the same bytes, because the design states no other fill for a numeric field. A file reader cannot recover the difference, and a file cannot carry "unresolved", so resolution must precede export. The ground `OMITTED_BOX_DECLARES_ZERO` (`core/casilla_value_absence.py:49-54`) states as law "A box the return leaves out declares zero"; no official text saying so was found, and it stands only as this inference about bytes.

### 7. Official sources make some boxes zero and some blank, and treat zero as a statement

Stated by the source:

- Zero by rule, Modelo 130 instructions (`aeat_official/instructions/modelo_130/files/modelo-130-instrucciones.html`; live page updated 11 September 2026 reads the same): casilla 04 "consigne el número cero" when 03 is negative (`:81`); casilla 12 "consigne el número cero (0)" (`:99`); casilla 18 zero on a complementaria with no earlier amount due (`:186`); a prior year without activity means its net income "son cero" (`:146`).
- Blank by rule, Modelo 303 instructions 2026: "se dejará en blanco la casilla 70", likewise 109 and 108 in stated rectification cases (URL under Sources). DR130 also treats blank as an answer: position 432, `blanco o "X"` (`:66`).
- Zero carries consequences: casilla 19 equal to zero leads to "Negativa" (`modelo-130-instrucciones.html:221`). In 303, "sin actividad" (no cuotas accrued or borne) and "resultado cero" are defined separately, though the design shares type `N` (DR303 `:136`).
- The filer of an unimported 130 must "cumplimentar todos los datos de la liquidación", and avisos differ from errors; the page says nothing of how boxes start.

Inference: no official blanket default of zero for an untouched box was found on the 130 pages or the 303 instructions, and each official zero is a rule on a condition, so a "defaulted zero" has no official counterpart. These legal zeros can be expressed as registry formulas or conditions.

### 8. Precedent supports empty boxes for awaited data, and limits what a blank can mean

AEAT's Renta guidance on changing option: "los importes han de ser cumplimentados manualmente, por lo que las casillas aparecerán vacías". AEAT's identity check treats a return whose casilla 505 "sea 0,00" as a real case. So AEAT's own products use empty for awaited amounts and treat `0,00` as a value, in the only two instances checked.

Evidence against a bare blank: the same mark means "not yet known" in that precedent and "the correct answer" in the 303 casilla 70 instruction. A blank alone cannot tell a filer which applies.

### 9. Options the evidence leaves open

- Bare blank for every no-figure state: fits the leaning and the AEAT look, fails finding 8 and needs a stated reason for accessibility. Weak.
- Blank value cell plus an adjacent state word: fits findings 6 to 8 and needs a small move on each surface. Favoured.
- Words or a dash in the value cell (today's desktop and PDF): keeps one column but reads as content. Workable only where no state column can exist.
- Zero everywhere with a blocker note (today's manual-box path): the operator's complaint, and contrary to the stricter records in finding 5. Disfavoured.

The ADR must settle a closed state set, what a zero must rest on, whether an empty ledger window blocks, and how unentered optional manual boxes behave.

Not investigated: authenticated AEAT forms (PRE130, PRE303, Renta WEB) in an attended session, so how they open an untouched box is unobserved; AEAT's worked-example PDF `Cap_7_303_4T.pdf`, not read for lack of a PDF extractor in the project environment; third-party Spanish tax software; BOE order texts beyond the bundled designs; designs beyond those cited, though zero-fill wording also appears in the Modelo 100 designs; and whether any M369 field reaches `absent_fill` from a seeded zero, since sampled fields are `kind = "binding"`.

The web quotes were read through a summarising fetch tool, not raw page bytes. Re-read them before using them as registry source citations.

## Sources

- `src/cadrumo/core/casilla_value_absence.py:22-74`
- `src/cadrumo/core/aggregation.py:726-739`
- `src/cadrumo/domain/calculations/registry/formula_initial_values.py:458-465`, `:525-526`, `:541-546`, `:562-563`
- `src/cadrumo/domain/calculations/registry/formula_runtime.py:149-153`, `:183`, `:747-772`
- `src/cadrumo/domain/calculations/registry/formula_runtime_ops.py:109`, `:161-165`
- `src/cadrumo/domain/calculations/registry/fixed_width_codec.py:554-619`
- `src/cadrumo/domain/calculations/registry/schema_exports.py:587-593`
- `src/cadrumo/domain/calculations/registry/ledger_renta_income_bindings.py:671-694`
- `src/cadrumo/application/aggregation/renta_imputation.py:67-71`
- `src/cadrumo/application/modelo/advisory_binding_value.py:72-101`
- `src/cadrumo/application/modelo/calculation_notes.py:22-26`, `:118-202`, `:282-305`
- `src/cadrumo/application/modelo/calculation_note_gate.py:64-83`
- `src/cadrumo/application/modelo/work_form_field_state.py:60-145`
- `src/cadrumo/application/modelo/work_form_wording.py:142-153`
- `src/cadrumo/application/modelo/value_presentation.py:15-17`
- `src/cadrumo/application/filing/_export_xml_dictionary_modelo100.py:79-91`
- `src/cadrumo/_data/corpus/aeat_official/`, design and instruction files cited in findings 6 and 7
- `native/desktop/frontend/src/components/modelo/form/ValueCell.tsx:59`
- `native/desktop/frontend/src/dev/fixtures/modelo/modelo-130-1T-es.json`
- `src/cadrumo/entrypoints/tui/modelo/workbench/casilla_list_values.py:91-92`, `:181-182`
- https://sede.agenciatributaria.gob.es/Sede/impuestos-tasas/impuesto-sobre-renta-personas-fisicas/modelo-130-irpf______esionales-estimacion-directa-fraccionado_/instrucciones.html
- https://sede.agenciatributaria.gob.es/Sede/ayuda/consultas-informaticas/presentacion-declaraciones-ayuda-tecnica/modelo-130.html
- https://sede.agenciatributaria.gob.es/Sede/todas-gestiones/impuestos-tasas/iva/modelo-303-iva-autoliquidacion_/instrucciones-2026/instrucciones-02-12-2t-4t-2026.html
- https://sede.agenciatributaria.gob.es/Sede/irpf/campana-renta/modificacion-declaracion-renta-2025-presentada/cambios-opcion.html
- https://sede.agenciatributaria.gob.es/Sede/ayuda/consultas-informaticas/firma-digital-sistema-clave-pin-tecnica/obtener-referencia-casilla-renta.html
