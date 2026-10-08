---
tags:
  - '#research'
  - '#modelo-editor-workbench'
date: '2026-09-30'
modified: '2026-10-03'
body_schema: 'body-v2'
body_hash: 'sha256:e74116ac161afb2b0d505fdc3bffe01e5762e79bb6928f031245104c752c27d5'
related:
  - "[[2026-09-30-modelo-editor-workbench-reference]]"
---

# `modelo-editor-workbench` research: `Filing journey, help content and language`

What does a non-developer's journey to file a modelo look like today, and what should it become? The evidence shows no screen presents one casilla's label, value, origin and help together, developer vocabulary throughout, and help coverage near 16 per cent; it favours one workbench per declaration with a stepper, next-action line and an attributed help card built from mechanical sources. Measured on 2026-09-30 against the live tree and the published authority; probe scripts ran in session scratch and were not retained, so every figure names the code or data it was measured from.

## Findings

Investigator: lens E. Date of measurement: 2026-09-30. Repository: `Y:\code\cadrumo-worktrees\tui`
(branch `feature/tui`, working tree carries another contributor's uncommitted edits to
`src/cadrumo/application/modelo/work_review.py` and its test; nothing in the repo was modified by
this investigation).

Evidence roots used below:

- `SHOTS` = `(session scratch, not retained)`
  (`svg\*.svg` screenshots, `text\*.txt` band dumps with focus chain and key band). 46 frames captured
  by `agent-e\capture.py`, which runs the real documentation sequences (`modelo-130-first-quarter`,
  `modelo-303-first-quarter`, `modelo-390-annual-2025`) in a hermetic temp sandbox, composes the
  installed workbench exactly as `aeat app tui` does, and walks Declarations -> row -> workspace page
  with the pilot. Language is forced per run with `override_settings(cadrumo_output_language=...)`.
- `REVIEW` = `Y:\code\cadrumo-worktrees\tui\.tmp-tui-visual-inventory\runs\current\text\` (the shared
  visual review run generated 2026-09-29T22:21Z; read only, not regenerated).
- Measurement scripts and outputs: `agent-e\measure_help.py` -> `help_measure.json`,
  `agent-e\allhelp.py` -> `allhelp.txt`, `measure2.py`, `cites.py`, `laws.py`, `sections.py`,
  `keys_modelo.txt` (en/es dump of every `tui.modelo.*`, `flows.modelo_workspace*`,
  `application.modelo.lifecycle*`, `operation.modal*` key). All registry measurements read the published
  authority at `.authority/` read-only (`CADRUMO_AUTHORITY_ROOT`), hydrated through the canonical
  `revision_for_context` / `revision` loaders, not raw TOML.

---

#### 1. Findings

##### 1.1 Today's journey, launch to filed/exported

| # | Step | What the user sees (es) | Evidence |
|---|------|-------------------------|----------|
| 1 | Home | Two columns: "Próximas acciones", "Declaraciones", "Agenda de presentación", "Preparación del libro", "Mensajes". Every block opens with a bare state word "Disponible". Period tokens leak: "M390 0A". The agenda already knows obligations and deadlines ("20/07 · M130 2T · Fuera de plazo") but a row does not create or open a declaration. | `REVIEW\home--ready__medium__dark.txt` |
| 2 | Declarations | "Áreas de declaraciones" table with a "Disponibilidad" column, then a create form with three free-text boxes whose placeholders look like values ("111", "2025", "1T / 0A", hardcoded at `src/cadrumo/entrypoints/tui/declarations/overview.py:60-64`), then the list. The list says "Estado local: Borrador" and "Resultado: No disponible" even for a 303 the sequence verified and filed, and for a 130 whose calculated result is 100.00. | `SHOTS\svg\130-a-declarations__120x36__es.svg`; `REVIEW\seq-modelo-303-first-quarter--declarations__large__dark.txt` |
| 3 | Workspace "Resumen" | A table titled "Página" listing five other pages (Entradas, Resultados, Verificación, Procedencia, Presentación); "Pasos siguientes sugeridos: Calcule esta unidad de trabajo; Revise el estado de esta unidad de trabajo; ..." (text, not buttons); then one bare input per writable casilla with placeholder "Casilla 06" (no label, value, help, type or state); then "Aplicar valores declarados", "Calcular", "Verificar", "Registrar presentación local", an export path box, artefact select, replace checkbox, "Exportar"; then "Dirección", "Coordenadas de revisión" (Aserción de revisión solicitada/almacenada), "Capacidades" (Disposición "? Sin medir") and "Detalles técnicos". | `SHOTS\text\130-full-overview__120x400__es.txt`, `SHOTS\svg\130-a-overview__{80x24,120x36,160x48}__es.svg` |
| 4 | Scale of step 3 | Bare inputs rendered before the Calculate button: 130 = 5, 349 = 16, 303 = 72, 390 = 241 scalars + 173 bindings ("Dato declarado modelo-390.page_1.datos-estadisticos-a-actividades-otras-1a"), 100 = 1,979 scalars + 2 bindings. At 80x24 the 130 screen shows 4 inputs and no action; 303 order is lexical: 02, 05, 08, 107, 108, 109, 111, 112, 12, 123 ... | counted from the focus chains in `REVIEW\seq-modelo-*--overview__large__dark.txt`; `SHOTS\text\303-a-overview__80x24__es.txt` |
| 5 | "Entradas" | One fold "Sin sección"; columns Dirección / Etiqueta / Valor / Tipo de entrada declarado. Etiqueta is empty on every row of every modelo (bug B1). Values mix "1000" and "500.00". 390 and 100 stop at 200 rows: "las restantes no son accesibles desde esta lectura". | `SHOTS\svg\130-a-inputs__120x36__es.svg`, `SHOTS\svg\390-lang-inputs__120x36__es.svg` |
| 6 | "Resultados" | Casilla / Valor only, sorted lexically, no labels: the 303 result (casilla 71, 105.00) sits among `iva.compensacion-aplicada-periodo` and other semantic ids. No "a ingresar / a devolver". | `SHOTS\svg\303-a-results__120x36__es.svg` |
| 7 | "Verificación" | "Verificación: ? Sin medir" shown above a list of findings for a verified 303; findings read "El modelo 100 2025 0A se suprime por declaración del contribuyente (previous_filing_binding)..." and "Una transacción repercutida no tiene evidencia justificativa (vínculo 71a5db2b...)"; Casilla column blank. "Ejes de preparación" lists "Vínculos preparados: No" and "Preparado (veredicto del productor): No" with no reason or action. | `SHOTS\text\303-full-verification__120x120__es.txt` |
| 8 | "Procedencia" | "Sujeto: sin atribuir" / "transaction:71a5db2bb891df29...", "100:2025:0A:irpf.previous_year_economic_activity_net_income". | `SHOTS\svg\130-full-provenance__160x80__es.svg` |
| 9 | "Presentación" | Two sentences that say what the page does not do, then a one-row "Capacidad / Disposición: Borrador de presentación ? Sin medir" table. The export controls are not here; they are on the Resumen. | `SHOTS\svg\130-full-filing__120x80__es.svg` |
| 10 | Calcular (303) | Modal "Datos de la autoliquidación del modelo 303" asks "¿Autoliquidación conjunta?" with an untranslated "Select" placeholder, every time Calculate is pressed. | `SHOTS\svg\303-act-overview-calculate__120x36__es.svg` |
| 11 | Calcular / Verificar success | The operation modal opens, and on success the workspace dismisses itself . The user lands back on the Declarations list, which still says "Borrador" / "No disponible"; the success notice was written to the dismissed screen. | `SHOTS\text\130-act-overview-calculate__120x36__es.txt`, `...-verify__...` |
| 12 | Registrar presentación local | Confirmation dialog (good copy, safe default focus on Cancelar). Enabled before verification; refusal comes after the press. | `SHOTS\svg\130-act-overview-file__120x36__es.svg` |
| 13 | Exportar | Type a filesystem path into a box, choose "Artefacto a exportar", press Exportar; a result screen lists SHA-256, byte size, software identity grade. | `overview.py:201-222`; `src/cadrumo/entrypoints/tui/modelo/export_result.py` |

Journey cost today for a 130 first quarter: 3 screens to reach the workspace, 1 page with 26 focus stops
before any calculation feedback, calculated values visible only on 2 other pages reached through a table,
the result figure never shown as "a ingresar", and 2 bounces back to the list (after Calculate and after
Verify). There is no screen where a user can see, for one casilla, its label, value, origin and help
together.

##### 1.2 Developer-language inventory (shown text -> proposed text)

Proposed text is es (tú register, see tone guide) with en in brackets. "Move" means the item belongs in the
technical-details drawer, not on the main surface.

| Locator / key | Shown today (es / en) | Proposed |
|---|---|---|
| `tui.modelo.edit.scalar` (`overview.py:187`) | "Casilla 06" / "Box 06" as the only field text | Row: "06  Retenciones e ingresos a cuenta   0,00 €   Lo introduces tú  [?]" (casilla row, lens B) |
| `tui.modelo.edit.binding` (`overview.py:193`) | "Dato declarado modelo-390.page_1.datos-estadisticos-a-actividades-otras-1a" / "Declared input ..." | The binding's own catalogue label, else the casilla label it feeds; the binding id moves |
| `tui.modelo.edit.apply` | "Aplicar valores declarados" / "Apply declared values" | "Guardar cambios" ("Save changes"); per-row edit modal saves directly, like the profile manager |
| `tui.modelo.destination.column` + list (`overview.py:318-322`) | "Página" table: Entradas, Resultados, Verificación, Procedencia, Presentación | Removed: replaced by the stepper and section navigator |
| `tui.modelo.recovery_action.operator.modelo.work.*` | "Calcule esta unidad de trabajo", "Revise el estado de esta unidad de trabajo" | Stepper next-action line: "Siguiente: calcula la declaración [F8]" ("Next: calculate the return") |
| `flows.modelo_workspace_overview.section.address` | "Dirección" / "Address" (for modelo/ejercicio/periodo) | Header line "Modelo 130 · 1.er trimestre 2026" ("Modelo 130 · Q1 2026") |
| `flows.modelo_workspace_overview.label.work_state` | "Estado de la unidad: Borrador" | Stepper state ("Rellenando", "Calculada", "Revisada", "Presentada") |
| `flows.modelo_workspace_overview.section.revision`, `label.requested_assertion`, `label.stored_assertion`, `tui.modelo.assertion.*` | "Coordenadas de revisión", "Aserción de revisión solicitada: Ninguna registrada" | Move. Main surface shows only "Formulario vigente: orden HAC/…/2025" in the help panel for the modelo |
| `flows.modelo_workspace_overview.section.capabilities`, `column.disposition`, `tui.modelo.disposition.*` | "Capacidades", "Disposición", "? Sin medir" | Removed as a table. Each capability becomes the enabled/disabled state of its action with a reason line ("Aún no se puede presentar: falta verificar") |
| `tui.modelo.capability.filing_draft_readiness` + `flows.modelo_workspace_filing.why.draft_structural` | "Borrador de presentación ? Sin medir" + "Cadrumo no puede saber de antemano..." | In the Presentar step: "Se comprobará al generar el fichero" (one line, no table) |
| `flows.modelo_workspace_inputs.column.address` | "Dirección" / "Address" (casilla id column) | "Casilla" / "Box" |
| `flows.modelo_workspace_inputs.column.input_kind` | "Tipo de entrada declarado" / "Declared input kind" | Column removed; the origin glyph + word lives in the row's state cell ("Calculada", "De tus registros", "Lo introduces tú") |
| `flows.modelo_workspace_inputs.section.unsectioned` | "Sin sección" / "Unsectioned" (every row, bug B1) | Section headings from the registry section path (section 2.7) |
| `flows.modelo_workspace_inputs.page_bounded`, `flows.modelo_workspace_results.page_bounded` | "las restantes no son accesibles desde esta lectura" | Never shown to users: the workbench pages by section, so no row is unreachable |
| `flows.modelo_workspace_inputs.values_unmeasured`, `input_kind_unmeasured`, `flows.modelo_workspace_verification.value.unmeasured` | "sin medir" / "not measured" | "Aún no calculada" ("Not calculated yet") for values; nothing for internal facets |
| `flows.modelo_workspace_results.not_applicable` | "Esta página aún no puede mostrar resultados calculados: no distingue las casillas calculadas de las que rellenas tú." | Removed (results are rows in the same list, marked "Calculada") |
| `flows.modelo_workspace_verification.section.readiness`, `column.axis`, `axis.*` | "Ejes de preparación", "Eje", "Vínculos preparados", "Preparado (veredicto del productor)" | Step 1 "Preparar datos" checklist: "Perfil completo ✓", "Libro clasificado ✖ 1 apunte sin clasificar [Ir]", "Justificantes ✖ 1 sin justificante [Ir]" |
| `flows.modelo_workspace_verification.evidence_carried` | "Referencias de respaldo y paso siguiente: Verifique esta unidad de trabajo" | Removed; the stepper carries the next step |
| `flows.modelo_workspace_verification.section.findings`, `column.message` | "Hallazgos", "Qué se encontró" | "Revisión: 1 impide presentar, 2 avisos"; each item "Casilla 05 · Falta el dato · [Ir a la casilla]" |
| `application.yml` finding templates `cross_period_operator_declared_suppression`, `transaction_evidence_missing_output`, `cross_period_non_official_local_chain` | "(previous_filing_binding)", "vínculo 71a5db2b…", "modelo 100 2025 0A" | No origin codes, hashes or period tokens in the sentence; name the thing ("el modelo 100 de 2025", "un apunte de ventas del 12/02") and add an [Ir] link; codes move to details |
| `flows.modelo_workspace_provenance.*` (`provenance.py:125-132`) | "Sujeto: sin atribuir", "Referencia de origen: transaction:…", "Resolutor" | Per casilla, in the help panel "De dónde sale": "Suma de 2 apuntes de ingresos del libro (ene–mar) [Ver apuntes]"; raw refs move |
| `tui.modelo.record_family.*` (`inputs.py:92-101`) | "Casillas / Vínculos / Fórmulas / Parámetros" as groupings | Not a user grouping; move |
| `application.modelo.lifecycle.export_destination_placeholder` | "Ruta de destino de la exportación" free text | Export dialog with a default folder and suggested file name ("130_2026_1T.txt") and a "Cambiar carpeta" control |
| `tui.modelo.export.artefact.label` | "Artefacto a exportar" / "Artefact to export" | "Qué quieres generar" ("What to create"): "Fichero para presentar en la AEAT", "Informe del cálculo (PDF)", "Informe del cálculo (CSV)" |
| `tui.modelo.export.result.label.file_sha256`, `software_identity_grade.*` | "SHA-256 del fichero", "Identidad de software en la cabecera del fichero" | Keep the warning sentence; move the hash and grade into details |
| `tui.modelo.m303_evidence.observed_at`, `attestation_attachment_id`, `attestation_sha256` | "Confirmado el ... (ISO 8601 con desfase UTC, por ejemplo 2025-04-01T12:00:00Z)", "Identificador de la atestación existente", "SHA-256 de la atestación existente" | A yes/no question with today's date defaulted; attestation identity handled by the application, never typed |
| `operation.modal.action.detach` | "Desvincular" / "Detach" | "Seguir en segundo plano" ("Keep running in the background") |
| `operation.modal.status.running` | Modal title "En curso" with no operation name | "Calculando el modelo 130 (1.er trimestre 2026)…" |
| `operation.modal.refusal.unknown_operation` | "El backend ya no conoce esta operación." | "Esta operación ya no existe. Vuelve a intentarlo." |
| `declarations/overview.py:60-64` (not catalogued) | Placeholders "111", "2025", "1T / 0A" | Modelo picker from the profile's obligations, ejercicio select, period select ("1.er trimestre (ene–mar)", "Anual") |
| `tui.declarations.column.availability`, `tui.home.availability.available` | "Disponibilidad: Disponible" on every navigation row and home block | Hide "Disponible" (the default); show a state only when it is not available, with the reason |
| `tui.home.address` / home agenda (`home.py:131`) | "M390 0A", "M130 2T" | "Modelo 390 · anual 2025", "Modelo 130 · 2.º trim." |
| Key band (`overview.py:158-159`, `inputs.py:134`, `results.py:79`, `filing.py:65`, `provenance.py:64`, `operations/modal.py:119`) | "q=quit_overview", "escape=request_close" (empty binding descriptions) | Described bindings: "Esc Volver", "F1 Ayuda" (section 2.9) |
| Textual footer | "^p palette" in every locale | Localize or hide the command palette hint |
| `m303_evidence` Select | "Select" placeholder in es | "Elige una opción" |
| `flows.manager.*` completeness line | "Al perfil le faltan 3 campo(s) obligatorio(s)" | Plural forms, not "(s)" (section 2.8) |

##### 1.3 Help content: what exists, measured

Per modelo, law-selected revision, hydrated casillas; "help" = `CasillaDefinition.get_help(locale)` returns
text; "= label" = help equal to the label after trimming a trailing full stop (`help_measure.json`):

| Modelo (revision) | Casillas | Help es | Help en | Help ca | Help hu | Help = label (es) | Required | Manual / bound / computed / projection-only |
|---|---|---|---|---|---|---|---|---|
| 303 (2026-y-siguientes) | 220 | 206 | 206 | 206 | 206 | 0 (but 90 start "Casilla N:" and paraphrase the label) | 2 | 72 / 52 / 33 / 61 |
| 130 (2019-y-siguientes) | 20 | 20 | 20 | 20 | 20 | 0 | 1 | 5 / 3 / 12 / 0 |
| 111 (2019-y-siguientes) | 30 | 0 | 0 | 0 | 0 | - | 0 | 19 / 9 / 2 / 0 |
| 115 (2019-y-siguientes) | 5 | 0 | 0 | 0 | 0 | - | 0 | 1 / 2 / 2 / 0 |
| 390 (2025) | 414 | 336 | 336 | 336 | 336 | 331 (en 318, ca 321, hu 322) | 2 | 241 / 152 / 19 / 0 |
| 100 (2025) | 2,249 | 224 | 224 | 224 | 224 | 1 | 7 | 1,979 / 52 / 216 / 0 |

- Labels exist for every casilla in all four locales for these six modelos (0 missing), so the blank
  Etiqueta column is a rendering bug (B1), not a content gap.
- Locale parity is complete: every locale has exactly the help count of es. The gap is authoring, not
  translation.
- Across the latest revision of all 58 modelos (`allhelp.txt`): 10,386 casillas, 2,103 with es help
  (20.2 %); 359 of those restate the label and 90 are "Casilla N: <label paraphrase>", so substantive
  help covers at most 1,654 casillas (15.9 %). 30 modelos have no help at all (including 111, 115, 036
  with 706 casillas, 220, 490, 349).
- 390's help is effectively absent: 331 of 336 entries repeat the label.

Other sources that can supply honest help, measured:

| Source | What it gives | Coverage measured |
|---|---|---|
| `legal_refs` on every casilla (`LegalReference`: kind, document_id, article, permalink, notes) | "Base legal: Ley 35/2006 del IRPF, art. 99 (BOE)" with a BOE permalink | 100 % of casillas in all six modelos carry legal refs. 1,420 legal refs point to 172 distinct documents (969 órdenes, 319 leyes, 72 reales decretos). Citation text is mechanical from kind + id ("orden-hac-1347-2024" -> "Orden HAC/1347/2024"); a short-name catalogue ("LIRPF", "LIVA", "LGT") needs 172 x 4 entries, 10 prefixes cover most use. `notes` are ASCII-folded internal Spanish ("aprobacion del Modelo 130") and must not be shown as help |
| Formula expressions | "Se calcula: [03] = [01] − [02]"; "[04] = máx(0; 20 % de [03])" with labels and parameter values | 389 formulas across latest revisions. Tree ops seen: add, subtract, multiply, divide, max, min, percent, negate, sum, if_then_else, comparisons; 130 and 100 need max/percent/if rendering, not only arithmetic (`measure2.py`) |
| `source_citations.required_text` on formulas | Verbatim snippets of the official AEAT instructions ("Casilla 28 ... suma de las retenciones e ingresos a cuenta ... por todos los conceptos"; "Casilla 04. ... 20 por 100 ... casilla 03 sea negativo ... cero") | 241 of 389 formulas carry a substantive quote (at least 3 words, not just "modelo 303"). All 33 303 formulas cite only "modelo 303" |
| `source_refs` -> corpus documents | Official instructions HTML, Renta manual PDF, record design, dictionary, XSD, with retrieval date | Casilla source refs by kind: record_design 8,028, manual_pdf 7,685, instructions 5,781, dictionary 4,285, form_spec 3,104, xsd 2,070. 20 of 58 modelos cite an instructions/manual source from their casillas. A development-time extractor could quote the instruction paragraph for each casilla (authoring, never runtime generation) |
| `semantic_role` | Classification (e.g. `irpf_pf_ingresos`, `dr303_23`) | Present on 219/220, 20/20, 30/30, 5/5, 409/414, 2,249/2,249; many 303 roles just restate the record-design id; useful for grouping similar casillas across modelos, not as text |
| `constraints` | Allowed range/sign/pattern/enum -> "Solo valores positivos", "Formato: CNAE de 4 dígitos" | 84/220 (303), 7/20 (130), 11/30 (111), 3/5 (115), 2/414 (390), 7/2,249 (100) |
| Bindings | "Se rellena con tus registros: ingresos del libro registro" | 52 / 3 / 9 / 2 / 152 / 52 bound casillas |
| Findings | Casilla-addressed verification messages | Only when a finding carries a casilla; today the column is blank for the observed findings |

##### 1.4 Language, localization and chrome findings

- Register is mixed within one flow. In the modelo workspace strings (`keys_modelo.txt`), es uses tú 12
  times ("Calcula esta declaración", "Lo introduces tú", "Se rellena con tus registros", "Vuelve a
  intentarlo") and usted 13 times ("Calcule esta unidad de trabajo", "Construya, verifique y exporte ...
  presente usted mismo", "vuelva a calcularla o ábrala", "Responda"). Catalan mixes "Calculeu" with "els
  teus registres". Heuristic counts over whole catalogues: es flows 37 tú / 1 usted, es profile 31 / 0,
  es application 22 / 53. Hungarian is consistently formal (Ön).
- F3 is "Tema" on home (`REVIEW\workbench-root--ready__medium__dark.txt`) and "Apariencia" on the
  workspace and profile manager.
- Money renders as raw decimal strings with inconsistent scale ("1000", "500.00", "0"), no thousands
  separator, no decimal comma in es/ca/hu, no currency.
- Period tokens appear raw ("1T", "0A", "4T") on home, declarations, workspace header and findings.
- Plural hacks: "campo(s) obligatorio(s)", "source modelo(s)".
- English says "Box" while the Spanish product domain term is casilla; acceptable, but help and search
  must accept both.
- Section tokens: 1,311 distinct section tokens, none catalogued (grounding reference). Measured for 303:
  72 distinct section paths, some of which are not sections but table cells:
  `iva/prorrata/actividad/fila_1..5/{cnae,operaciones_total,operaciones_con_derecho,tipo,porcentaje}` (a
  5x5 grid) and `iva/deducciones/sectores_diferenciados/sector_1..2/{domestic_current_base,...}` (English
  tokens inside Spanish paths). 111 is ten 3-casilla rows (perceptores / percepciones / retenciones), which
  is the official 111 table shape. 130 uses `computed_carry_forward` (English) for one row.
- Casilla numbers are not always numbers: `number` equals the semantic id for 38 of 303's casillas, 50 of
  390's, 1 of 130's (`saldo-negativo-fin-periodo`); 100 has non-numeric numbers such as `A`, `*98`.
  Any "Casilla NN" presentation needs a label-only fallback for these.

---

#### 2. Proposed design

##### 2.1 Principles

1. One screen per declaration. Everything the user does to file one modelo happens in the workbench;
   other screens are modals over it (edit, import review, operation progress, export, help detail).
2. The form speaks the form's language: casilla number + official label, grouped by the modelo's own
   sections, in the official order, with values formatted as money.
3. Always answer "what do I do next?" in one line, with the key that does it.
4. Every state is words plus a glyph, never colour alone (ADR D8).
5. Honest help: official text is quoted and attributed; Cadrumo explanations are labelled as Cadrumo's;
   nothing about tax law is generated at runtime.
6. Raw identifiers exist, one key away, in a technical drawer; never on the main surface.

##### 2.2 Target journey and screen map

```
Home ──(agenda row / "Mis declaraciones")──> Declaraciones
  │                                              │ Enter on a row, or "Nueva declaración" (modal:
  │                                              │ modelo from your obligations, ejercicio, periodo)
  └──(agenda row "M130 2T · Fuera de plazo")─────┴──> WORKBENCH (one screen, per declaration)
                                                        ├─ modal: Editar casilla (typed editor, lens C)
                                                        ├─ modal: Importar / revisar datos (lens D)
                                                        ├─ modal: Operación en curso (existing OperationModal)
                                                        ├─ modal: 303 datos de la autoliquidación (only when needed)
                                                        ├─ modal: Generar fichero / informe (export)
                                                        ├─ modal: Confirmar registro de presentación local
                                                        └─ drawer: Detalles técnicos (ids, producers, provenance refs)
```

What folds into the workbench:

| Today | In the workbench |
|---|---|
| Overview: address, revision, capabilities, suggestions | Header line + stepper + next-action line; capabilities become action enablement with reasons |
| Overview: bare edit inputs + "Aplicar valores declarados" | Casilla rows; Enter opens the typed editor; save per casilla |
| Inputs page | The casilla list itself (all input kinds, grouped by section) |
| Results page | Same list; calculated rows are marked "Calculada"; the result casilla is pinned in the header ("Resultado: 100,00 € a ingresar") |
| Verification page | Step "Revisar": issue list panel with [Ir a la casilla]; readiness axes become step 1's checklist |
| Provenance page | Help panel section "De dónde sale" per casilla; raw refs in the drawer |
| Filing page + export controls | Step "Presentar": generate the file, what to do at the AEAT, record the local filing |
| After-success dismiss to the list | Stay; refresh in place; stepper advances; toast "Calculada · Resultado 100,00 € a ingresar" |

This changes accepted ADR D1 (one destination per page). The destination ids can survive as anchors
(`modelo.workspace.inputs` -> workbench focused on the first section; `...verification` -> workbench with
the Revisar panel open) so routing identity is preserved while the pages disappear. That is an amendment
decision for the `modelo-editor-workbench` ADR, not a UI detail.

##### 2.3 Workbench layout

Mockups use synthetic values; deadlines and counts are illustrative.

Regions: (1) header: modelo name, period, deadline, result; (2) stepper + next action; (3) section
navigator; (4) casilla list; (5) help panel; (6) key footer. Layout adapts by width; all regions stay
reachable by keyboard at every size (D8).

80x24: navigator collapses into a one-line section bar; help panel is an overlay (F1) or a two-line
description strip under the list.

```
 Modelo 130 · Pago fraccionado IRPF · 1.er trim. 2026      Plazo 20/04 · 12 días
 ✓Preparar ●Rellenar 3 ○Calcular ○Revisar ○Presentar    Resultado: sin calcular
 Siguiente: revisa 3 casillas que introduces tú (06, 16, 18)             [F8 Ir]
 ◀ I. Actividades en estimación directa  4/7 ▶                   Sección 1 de 4
 ──────────────────────────────────────────────────────────────────────────────
  01 Ingresos                               1.000,00 €  ⇄ De tus registros    ?
  02 Gastos                                   500,00 €  ⇄ De tus registros    ?
  03 Rendimiento neto                         500,00 €  = Calculada           ?
  04 Importe del pago fraccionado             100,00 €  = Calculada           ?
  05 Pagos fraccionados anteriores              0,00 €  ⇄ De tus registros    ?
▶ 06 Retenciones e ingresos a cuenta               —    · Sin revisar         ?
  07 Resultado de la sección I                     —    = Pendiente           ?
 ──────────────────────────────────────────────────────────────────────────────
 06 · Retenciones y pagos a cuenta soportados en el trimestre por actividades
 en estimación directa. Explicación de Cadrumo · F1 para más
 F1 Ayuda  Intro Editar  / Buscar  [ ] Sección  F8 Siguiente paso  Esc Volver
```

120x36: navigator on the left, list in the middle, help strip below (6 lines).

```
 Modelo 130 · Pago fraccionado IRPF, estimación directa · 1.er trimestre 2026 (ene–mar)    Plazo 20/04/2026 · 12 días
 ✓ Preparar datos ── ● Rellenar (3 sin revisar) ── ○ Calcular ── ○ Revisar ── ○ Presentar    Resultado: sin calcular
 Siguiente: revisa las casillas que introduces tú: 06, 16, 18 (escribe el importe o confirma 0).  [F8 Ir]
┌ Secciones ─────────────────┐┌ I. Actividades económicas en estimación directa ───────────────────────────────────────┐
│▶ I. Estimación directa   · ││  Nº  Casilla                                  Importe   Estado                         │
│  II. Agrícolas, ganaderas  ││  01  Ingresos                              1.000,00 €   ⇄ De tus registros   [?]       │
│  III. Total liquidación    ││  02  Gastos                                  500,00 €   ⇄ De tus registros   [?]       │
│  Resultado                 ││  03  Rendimiento neto                        500,00 €   = Calculada          [?]       │
│                            ││  04  Importe del pago fraccionado            100,00 €   = Calculada          [?]       │
│Filtro                      ││  05  Pagos fraccionados anteriores             0,00 €   ⇄ De tus registros   [?]       │
│[x] Todas   [ ] Pendientes  ││▶ 06  Retenciones e ingresos a cuenta              —     · Sin revisar        [?]       │
│[ ] Solo obligatorias       ││  07  Resultado de la sección I                    —     = Pendiente          [?]       │
│                            ││                                                                                        │
│Leyenda                     ││                                                                                        │
│✎ Lo introduces tú          ││                                                                                        │
│⇄ De tus registros          ││                                                                                        │
│= Calculada                 ││                                                                                        │
│✱ Cambiada por ti           ││                                                                                        │
│! Obligatoria, falta        ││                                                                                        │
└────────────────────────────┘└────────────────────────────────────────────────────────────────────────────────────────┘
┌ Casilla 06 · Retenciones e ingresos a cuenta ────────────────────────────────────────────────────────────────────────┐
│ Qué es   Retenciones y pagos a cuenta soportados en el trimestre por actividades en estimación directa. (Cadrumo)    │
│ Dónde    Facturas emitidas con retención de IRPF del trimestre; certificados de retenciones de tus clientes.         │
│ Base     Ley 35/2006 del IRPF, art. 99 · Real Decreto 439/2007, art. 110 (BOE) · F1 para ver todo                    │
└──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
 F1 Ayuda completa  Intro Editar  / Buscar o ir a casilla  F8 Siguiente paso  F9 Acciones  Ctrl+T Detalles  Esc Volver
```

160x48: three panes; help panel is a full column with all sections of the help card; the issue list
(Revisar) opens in the same right column.

```
 Modelo 303 · IVA autoliquidación · 1.er trimestre 2026 (ene–mar)                    Plazo 20/04/2026 · quedan 12 días       Resultado: 105,00 € a ingresar
 ✓ Preparar datos ── ✓ Rellenar ── ✓ Calcular ── ● Revisar (1 aviso) ── ○ Presentar                                     Calculada hoy 10:42 · datos al día
 Siguiente: revisa 1 aviso y verifica la declaración.  [F8 Verificar]
┌ Secciones ─────────────────────┐┌ IVA devengado · Régimen general ──────────────────────────────────┐┌ Casilla 27 · Total cuota devengada ────────────────┐
│  Identificación             ✓  ││  Nº   Casilla                            Base         Cuota        ││ = Calculada · 210,00 €                             │
│▶ IVA devengado              ✓  ││  01   Régimen general 4 %          0,00 €       0,00 €  ⇄        ││                                                    │
│    Régimen general          ✓  ││  04   Régimen general 10 %         0,00 €       0,00 €  ⇄        ││ QUÉ ES                                  (Cadrumo)  │
│    Recargo de equivalencia  ○  ││  07   Régimen general 21 %     1.000,00 €     210,00 €  ⇄        ││ Total de la cuota de IVA devengada en el periodo.  │
│    Inversión sujeto pasivo  ○  ││  10   Adquisiciones intracom.      0,00 €       0,00 €  ⇄        ││                                                    │
│  IVA deducible              ✓  ││  ...                                                             ││ CÓMO SE CALCULA               (fórmula registro)   │
│  Prorrata                   –  ││  27   Total cuota devengada                   210,00 €  =         ││ [27] = [03] + [06] + [09] + [11] + [13] + ...      │
│  Resultado                  ✓  ││                                                                  ││                                                    │
│  Información adicional      –  ││                                                                  ││ TEXTO OFICIAL        (Instrucciones AEAT, 303)     │
│                                ││                                                                  ││ (no hay cita oficial para esta casilla)            │
│ Revisión                       ││                                                                  ││                                                    │
│  ! 1 aviso              [Ver]  ││                                                                  ││ BASE LEGAL                                         │
│                                ││                                                                  ││ Ley 37/1992 del IVA, arts. 88, 90, 91 · BOE ↗      │
│                                ││                                                                  ││ Orden EHA/3786/2008, art. 1 (aprueba el modelo)    │
│                                ││                                                                  ││                                                    │
│                                ││                                                                  ││ SE USA EN                                          │
│                                ││                                                                  ││ 46 Resultado régimen general                       │
└────────────────────────────────┘└──────────────────────────────────────────────────────────────────┘└────────────────────────────────────────────────────┘
 F1 Ayuda  Intro Editar  / Buscar o ir a casilla  [ ] Sección  F8 Siguiente paso  F9 Acciones  Ctrl+T Detalles técnicos  Esc Volver
```

Grid-shaped sections (303 prorrata rows, 111 per-category rows, base/cuota pairs) render as a table with
column headers taken from the path's last segment, as the official form does (lens A owns detection).

##### 2.4 Stepper and next-action logic

Five steps. Verification is the action that completes Revisar; filing is local recording plus human
handoff, never remote submission (ADR D7 wording).

| Step | Done when | Signals (exist today unless noted) | Next-action line when current |
|---|---|---|---|
| 1 Preparar datos | profile ready, ledger classified, evidence present, bound sources resolved | readiness axes `profile_ready`, `ledger_ready`, `binding_ready` (verification facet); home zone "Preparación del libro" counts | "Clasifica 1 apunte del libro [F8 Abrir libro]" / "Completa tu perfil: falta el régimen de IVA [F8]" |
| 2 Rellenar | every manual casilla is either entered or explicitly confirmed ("Confirmar 0" / "No aplica"), no required casilla missing, no invalid value | `required` is too sparse to drive this alone: 130 marks only casilla 02 (bound) required, 303 only ejercicio and periodo; so the step counts unreviewed manual casillas. Needs the manual value source (current revision's `input_values_by_casilla_id`), a per-casilla "confirmed empty/zero" record (new, lens C) and `required` carried by the review (not carried today) | "Revisa 3 casillas que introduces tú [F8 Ir]"; count in step label "Rellenar (3 sin revisar)" |
| 3 Calcular | a current calculation revision exists and no edit/import happened after it | calculation revision id and timestamps vs edit/import timestamps (stale flag is new, lens C) | "Calcula la declaración [F8]"; after edits "Hay cambios sin calcular [F8 Recalcular]" |
| 4 Revisar | no blocking finding; verification receipt for the current calculation revision | finding severities; verification capability | "Corrige 1 problema que impide presentar [F8 Ir]" / "Verifica la declaración [F8]" |
| 5 Presentar | file generated for the current revision and local filing recorded | export result, local filing record, AEAT sync observation (home agenda already shows "AEAT: presentación observada") | "Genera el fichero para la AEAT [F8]" -> "Preséntalo en la Sede y registra la presentación [F8]" -> "Presentada · observada en la AEAT ✓" |

Rules:

- The next action is the first unmet condition in the order above; a workspace-level refusal (profile
  incomplete, authority grade unavailable, ambiguous target) preempts all steps and is shown as one
  sentence with its catalogued recovery action as a button, never as a "Disposición" table.
- A step is ✓ done, ● current, ! blocked (with reason), ○ not yet, – not applicable (e.g. no prorrata).
- F8 always runs the next action; an action that would destroy or submit asks for confirmation.
- Actions that are not yet possible stay visible in the F9 menu, disabled with the reason (D7):
  "Registrar presentación local — primero verifica la declaración".
- The header always shows the result casilla(s) the registry marks as the settlement result, with the
  sign in words ("a ingresar", "a devolver", "a compensar", "sin actividad"); when not calculated it says
  "sin calcular", never "0".
- The deadline comes from the registry deadline windows the home agenda already uses.

First-time user:

- Empty Declaraciones: "Aún no tienes declaraciones. Según tu perfil te tocan: Modelo 130 (trimestral),
  Modelo 303 (trimestral). [Crear Modelo 130 · 1.er trimestre 2026]". Obligations come from the same
  calendar/agenda projection as home.
- First open of a workbench: a dismissible three-line intro above the stepper ("Así se rellena: revisa
  los datos que vienen de tus registros, completa las casillas marcadas con !, calcula, revisa y genera
  el fichero. F1 explica cualquier casilla.") Remembered per profile.
- Empty section: "No hay nada que rellenar aquí para tu caso" when all rows are not applicable; not an
  empty table.
- Nothing is a dead end: every refusal names what to do and offers the key.

##### 2.5 Help panel content model

```
CasillaHelpCard
  identity        number (or none), official Spanish label, localized label, section path headings
  state           value (formatted), origin (entered / from records / calculated / changed by you),
                  required, missing vs proven zero vs not applicable, stale
  what            catalogue help  -> tagged "Explicación de Cadrumo"
  where           catalogue "where to find it" (new optional key, same identity as help)
  from_records    bound source: which records, how many, period; override state and the original value
  how_calculated  rendered registry formula with labels and parameter values -> tagged "Fórmula del registro"
  official_text   source_citations quotes + source title + retrieval date -> tagged "Texto oficial de la AEAT"
  legal_basis     legal_refs rendered "Ley 35/2006 del IRPF, art. 99" + BOE link -> tagged "Base legal"
  constraints     allowed range / format in words
  uses / used_by  formula precedents and dependents, each a jump link
  issues          findings addressing this casilla
  technical       ids, semantic_role, binding ids, formula id (drawer only)
```

Precedence and honesty:

1. Official text is shown verbatim and attributed; it is never paraphrased at runtime.
2. Cadrumo-authored help is always tagged as such, in every locale; its translation is catalogue text,
   not machine output at runtime.
3. When a casilla has no substantive help (help missing, equal to the label, or a "Casilla N:" restatement),
   the panel shows the parts that exist (formula, official text, legal basis, origin) and one line: "Aún
   no hay una explicación de Cadrumo para esta casilla." It never fabricates one.
4. The legal-basis line is mechanical from the reference id and kind plus a 172-document short-title
   catalogue; the internal `notes` field is never shown.
5. A local calculation is labelled as local ("Calculado por Cadrumo con tus datos; no es un valor de la
   AEAT"), per the no-silent-under-declaration rule.

Closing the gap honestly, in order of value per effort:

- Quality gate first: a catalogue check that flags help equal to its label or matching "Casilla N: <label
  words>" so 359 + 90 restatements stop counting as coverage (they should read as "no help").
- Mechanical sources for all modelos now: formula rendering (389 formulas), legal basis (100 % of
  casillas), constraints, binding origin. This alone gives 111 and 115, which have zero help, a useful
  panel for every casilla.
- Authoring campaign ordered by filer volume: 111, 115, 390 (replace restatements), 303 (replace "Casilla
  N:" paraphrases), 100 by section. Each entry grounded in the official instructions via the existing
  corpus; development tooling can extract the instruction paragraph per casilla number from the
  instructions HTML (20 of 58 modelos cite one) for an author to adapt; the extracted paragraph may also
  be stored as an attributed official quote.
- A per-modelo help coverage number (substantive help / casillas) shown in development reports, not to
  users.

##### 2.6 Section headings

- Add catalogue keys for section tokens under the modelo's schema namespace with the same fallback chain as
  labels; es text copied from the official form's section titles (e.g. 130 "I. Actividades económicas en
  estimación directa", "II. Actividades agrícolas, ganaderas, forestales y pesqueras", "III. Total
  liquidación"); en/ca/hu translated.
- Start with the tokens used by the most-filed modelos (the grounding reference measures 180 tokens for
  the nineteen most-used consumer and withholding modelos); gate completeness per modelo like labels.
- Until a token is catalogued, show the Spanish token humanized ("Actividades economicas estimacion
  directa") marked with a subtle "(ES)" in non-es locales; never the raw snake_case.
- Tokens that are grid axes (`fila_N`, `sector_N`, column tokens) are not headings; they become row and
  column headers (lens A).
- Normalize the English tokens (`domestic_current_base`, `computed_carry_forward`) in the registry to the
  Spanish stem convention before cataloguing, so each concept has one key.

##### 2.7 Tone guide

Voice: second person, direct, present tense, one idea per sentence. Name the user's objects (declaración,
casilla, apunte, fichero, AEAT), never the system's (unidad de trabajo, capacidad, disposición, faceta,
productor, artefacto, vínculo, resolutor, backend, materialización, aserción).

| Locale | Register | Notes |
|---|---|---|
| es | tú, consistently (matches the profile manager and flows, the product's reference surface) | Casilla labels keep the AEAT official wording verbatim. "Presentar" only for the real act at the AEAT; local recording is "registrar la presentación" |
| ca | tu, consistently (replace "Calculeu/Verifiqueu") | Keep "casella" for casilla, AEAT terms as proper nouns |
| hu | Ön (already consistent) | Keep "rovat" for casilla; AEAT, BOE, modelo names unchanged |
| en | you | "Box" for casilla with "(casilla)" in help; Spanish tax terms italicised in help when there is no English equivalent |

State vocabulary (one word or short phrase per state, plus glyph; the glyphs have ASCII fallbacks):

| State | Glyph | es | en | ca | hu |
|---|---|---|---|---|---|
| Entered by the user | ✎ | Lo introduces tú | You enter it | L'introdueixes tu | Ön adja meg |
| From records (bound) | ⇄ | De tus registros | From your records | Dels teus registres | Az Ön nyilvántartásából |
| Calculated | = | Calculada | Calculated | Calculada | Számított |
| Changed by the user over a record value | ✱ | Cambiada por ti | Changed by you | Canviada per tu | Ön módosította |
| Required and missing | ! | Obligatoria, falta | Required, missing | Obligatòria, falta | Kötelező, hiányzik |
| Manual, not yet entered or confirmed | · | Sin revisar | Not reviewed | Sense revisar | Nincs átnézve |
| Optional and empty (confirmed) | ○ | Vacía (confirmada) | Empty (confirmed) | Buida (confirmada) | Üres (megerősítve) |
| Proven zero | (value) | 0,00 € | €0.00 | 0,00 € | 0,00 € |
| Not applicable | – | No aplica | Not applicable | No s'aplica | Nem alkalmazandó |
| Needs recalculation | ⟳ | Pendiente de recalcular | Needs recalculation | Cal recalcular | Újraszámítás szükséges |
| Blocks filing | ✖ | Impide presentar | Blocks filing | Impedeix presentar | Akadályozza a benyújtást |
| Warning | ▲ | Aviso | Warning | Avís | Figyelmeztetés |

Rules: missing is "—" with a word, never blank and never "0"; proven zero is a formatted zero. Money uses
locale formatting (es/ca/hu "1.234,56 €" with non-breaking space in hu "1 234,56 €"; en "€1,234.56").
Periods are words: "1.er trimestre (ene–mar)", "Anual", "Enero"; tokens ("1T", "0A") only in the drawer.
Plurals through catalogue plural forms, never "(s)". Errors follow "what happened · why · what to do"
and end with an action; codes go to the drawer.

##### 2.8 Keyboard hints

- Every binding carries a catalogue description; the footer shows five to seven context keys and never an
  action method name.
- Global keys stay as today (F2 idioma, F3 tema; unify "Tema" vs "Apariencia" to one word).
- Workbench keys: F1 ayuda, Intro editar, / buscar o ir a casilla (typing a number jumps to that casilla,
  like the AEAT forms' "Ir a casilla"), `[` `]` sección anterior/siguiente, F8 siguiente paso, F9 menú de
  acciones, Ctrl+T detalles técnicos, Esc volver. Check for conflicts with the account chrome keys F4–F6
  and F10 shown on home before adopting F8/F9.
- Localize or hide Textual's "^p palette".

##### 2.9 Acceptance

- Four locales (es, en, ca, hu) x three geometries (80x24, 120x36, 160x48) x two themes, for the
  workbench, every modal and the declaration list, on 130, 303, 111, 390 and 100 (the last two for scale
  and depth), using the documentation sequences as the data source.
- Band assertions on the captured text (the frame capture already exposes text, focus chain and key
  band): no visible token matching a semantic casilla id, binding id, snake_case section token, hex digest
  of 12+ characters, period token or `method_name` outside the technical drawer; every casilla row has a
  non-empty label; every section heading resolves from the catalogue or the marked fallback; the key band
  has no empty descriptions.
- At 80x24 the next-action line and its key are visible without scrolling.
- After Calculate, Verify and Export, the workbench is still the active screen and the stepper advanced.

##### 2.10 AEAT web forms, from my own knowledge (not verified today; details may be dated)

- Modelo 303 web form / Pre-303 service: pages that mirror the official form (identification, liquidation
  pages, result, payment/refund document); computed casillas are shown but read-only; "Validar" produces a
  list of errors (block) and avisos (warn), each linking to its casilla; a draft can be saved. Pre-303
  prefills from the VAT record books.
- Renta WEB: a persistent result bar ("resultado de la declaración") visible on every page; a left
  menu by apartado; "Ir a casilla" search by number; data from "datos fiscales" is loaded into the
  declaration and the user can modify it; per-casilla or per-apartado help opening the manual text;
  validation lists errors/avisos with navigation; a summary page before filing; "Vista previa" PDF.
- Sociedades WEB (200): the same page-per-official-page structure with numbered casillas and a validation
  list.

Borrow: the persistent result bar; page/section navigation that mirrors the official form; "Ir a casilla"
by number; errors vs avisos with jump links; computed casillas visibly read-only; imported values shown as
such and changeable with the change remembered; a summary before generating the file. Do not borrow:
modal-heavy navigation, help that only exists as a separate PDF.

---

#### 3. Suggestions ranked by user value vs effort

| Rank | Suggestion | Value | Effort | Notes |
|---|---|---|---|---|
| 1 | Fix label/section lookup on the inputs page (B1) | High | XS | One-line key mismatch; instantly gives every row its label |
| 2 | Stay on the workspace after success, refresh in place, keep the notice (B3) | High | S | Removes the two bounces |
| 3 | Numeric/official casilla order everywhere (B2) | High | S | Use export offset / casilla number order (lens A) |
| 4 | Locale money and period formatting; "—" for missing | High | S | Core formatter exists for decimals |
| 5 | Header result bar with "a ingresar / a devolver" | High | S | Registry knows the settlement casilla |
| 6 | Rewrite the developer-language keys in 1.2 and give every binding a description | High | S–M | Catalogue-only for most rows; 4 locales |
| 7 | Workbench v1: header, stepper, next action, section navigator, casilla rows (label, value, origin, state), help strip; old pages as anchors | Very high | L | Composes lenses A–D; ADR D1 amendment |
| 8 | Help panel with mechanical sources (formula, legal basis, constraints, origin, official quotes) | High | M | Covers every casilla of every modelo without new prose |
| 9 | Declarations: create from obligations/agenda with pickers; open the new declaration | High | M | Replaces three free-text boxes |
| 10 | Revisar panel: findings with casilla links, no raw codes; readiness as a checklist with actions | High | M | Application message templates need rewording |
| 11 | Section heading catalogue for the most-filed modelos, then all | Medium–high | M (catalogue) | 180 tokens first |
| 12 | Help quality gate + authoring campaign (111, 115, 390, 303, 100) | High long-term | L (content) | Grounded in official instructions |
| 13 | Export dialog with default folder and file name; artefact names in plain words | Medium | S | |
| 14 | 303 evidence: ask only in the period that needs it, with defaults | Medium | S–M | |
| 15 | Unify register (tú/tu/Ön/you) and plural forms across catalogues | Medium | M | Mechanical review per locale |
| 16 | Technical drawer consolidation (ids, producers, provenance refs) | Medium | S | Keeps honesty without noise |

---

#### 4. Bugs noted (not fixed)

| ID | Bug | Evidence |
|---|---|---|
| B1 | Inputs page never shows labels and puts every row under "Sin sección": the lookup keys are `str(record.reference)`, which renders as `"kind='casilla' casilla_id='01'"`, while rows are keyed by the bare casilla id. | the former source file, `:211`, `:235`, `:245`; verified with `str(ModeloWorkspaceCasillaReferenceV1(casilla_id='01'))` |
| B2 | Casillas ordered as strings ("107" before "11") on the overview edit list and the results/inputs tables. Which layer sorts was not isolated. | `SHOTS\text\303-a-overview__80x24__es.txt`, `303-a-results__120x36__es.txt` |
| B3 | Successful Calculate/Verify dismisses the workspace (`self.dismiss(None)`) and the success notice is written to the dismissed screen. | the former source file; `SHOTS\text\130-act-overview-calculate__120x36__es.txt` |
| B4 | Declarations list shows "Borrador" and "Resultado: No disponible" for calculated, verified and filed declarations. | `src/cadrumo/entrypoints/tui/declarations/overview.py:84-97`; `REVIEW\seq-modelo-303-first-quarter--declarations__large__dark.txt` |
| B5 | Verification page states "Verificación: ? Sin medir" and "Preparado (veredicto del productor): No" for a 303 the sequence verified and filed, while listing its findings. | `SHOTS\text\303-full-verification__120x120__es.txt` |
| B6 | Finding messages interpolate raw origin codes, transaction digests and period tokens; the Casilla column is empty for them. | `src/cadrumo/locales/en/application.yml:1159-1161` (`cross_period_operator_declared_suppression`), `:1233`; `SHOTS\text\130-full-verification__120x120__es.txt` |
| B7 | Key band exposes method names ("q=quit_overview", "escape=request_close") because bindings have empty descriptions. | `overview.py:158-159`, `inputs.py:134-135`, `results.py:79-80`, `filing.py:65-66`, `provenance.py:64-65`, `src/cadrumo/entrypoints/tui/operations/modal.py:119` |
| B8 | Lifecycle buttons are always enabled regardless of capability; e.g. "Registrar presentación local" before verification refuses after the press. Accepted ADR D7 requires visible disabled actions with reasons. | `overview.py:198-222` |
| B9 | Untranslated UI strings: Textual "palette" footer in every locale; Select placeholder "Select" in the es 303 evidence form. | `SHOTS\svg\303-act-overview-calculate__120x36__es.svg` |
| B10 | F3 is "Tema" on home and "Apariencia" on workspace/profile. | `REVIEW\workbench-root--ready__medium__dark.txt` vs `SHOTS\text\130-a-overview__120x36__es.txt` |
| B11 | Installed workbench composition aborts with `StoredCalculationDriftError` for the `modelo-100-renta-2025` sequence: a stored non-enum, non-date binding override that is not a decimal raises in `_persisted_decimal_bindings`, and one declaration's failure stops the whole root generation (no home, no list). Observed on the current working tree, which carries uncommitted edits to `work_review.py`; the 2026-09-29 review run rendered this sequence, so it may be in-flight work. | `agent-e\cap100.log`; `src/cadrumo/application/modelo/_work_review_assembly.py:193-196`; `src/cadrumo/application/workbench_generation.py:828`; `src/cadrumo/entrypoints/tui/launcher.py:416` |
| B12 | Inputs/results pages cap at 200 rows and say the rest are unreachable (390, 100). | `SHOTS\svg\390-lang-inputs__120x36__es.svg` |
| B13 | Money shown as raw strings with mixed scale ("1000", "500.00"), no locale separators or currency. | `SHOTS\text\130-a-inputs__120x36__es.txt` |
| B14 | Suggested next steps are CLI-style recovery phrases, not actions; "Revise el estado de esta unidad de trabajo" has no on-screen target. | `overview.py:701-720` |
| B15 | Declaration create form uses hardcoded, unlocalized placeholders that look like entered values; after creation only a notice is shown (whether the list refreshes was not verified). | `declarations/overview.py:60-64`, `:180-190` |
| B16 | Known from the grounding reference (lens C owns): a second edit silently drops earlier manual values; the edit baseline goes stale after 5 minutes but is admitted once at composition; binding override removal is refused. | `src/cadrumo/application/modelo/_edit_execution.py:102`, `:251`; `edit_admission.py:57`; `launcher.py:1035` |
| B17 | Help content defects: 390 help repeats the label for 331 of 336 casillas (es); 90 of 303's help entries are "Casilla N: <paraphrase>". | `agent-e\help_measure.json`, `allhelp.txt` |
| B18 | Registry `number` equals the semantic id for 38 (303), 50 (390) and 1 (130) casillas, so "Casilla NN" cannot be shown for them. | `measure2.py` output |
| B19 | Section paths mix English tokens (`sector_1/domestic_current_base`, `computed_carry_forward`) into Spanish paths. | `sections.py` output |
| B20 | Spanish and Catalan register mix within the same flow (tú/usted, tu/vós). | section 1.4 |

---

#### 5. Risks and open questions

- ADR D1 lists one destination per page and the C1–C5 cohort receipts are built around them. Folding pages
  into one workbench needs an accepted amendment (keep ids as anchors or retire them atomically under
  `no-legacy-compatibility`).
- The stepper needs signals the projection does not carry today: `required` per casilla, manual vs
  materialized origin, a stale flag after edits, the settlement result casilla and its sign. Without them
  the stepper would guess; it must show "unknown" rather than a false ✓.
- Filing language: "Presentar" must not imply Cadrumo submits to the AEAT. The step ends with a handoff
  and a local record; if remote filing arrives later, it is a separate guarded action.
- Help honesty: the extracted-instruction workflow must stay an authoring aid with attribution and
  retrieval date; any runtime paraphrase or AI-generated tax text is out.
- `required` is sparse (283 of 13,046 authored rows per the grounding reference; 1 in 130, 2 in 303, both not manual), so a "required missing" count alone would show a false "all filled". The Rellenar step must count unreviewed manual casillas, which needs an explicit "confirm zero / not applicable" act per casilla; this is also what keeps an untouched zero from being a silent under-declaration.
- Scale: 100 has 2,249 casillas and 169 section paths; the navigator needs search, "only pending", and
  collapsed deep sections to stay usable at 80x24.
- Register choice (tú vs usted) is a product decision; the measurements favour tú for UI copy, but some
  users expect usted in tax software. Hungarian formal Ön stays.
- Glyph support: ⇄ ✱ ⟳ ▲ may be missing in some terminal fonts; the render tool reports missing glyphs,
  so each glyph needs an ASCII fallback and the state word is always present.
- B11 may be in-flight work in the shared tree; re-measure on a clean HEAD before filing it.
- Open: which casilla is "the result" per modelo (registry flag or semantic role); whether deadline windows
  are available for every modelo shown (a prior note says some filing periods lack a window).

---

#### 6. Overlap notes for lenses A–D

- A (form model / grouping): I depend on official ordering (not lexical), section headings from a
  catalogue, grid detection for `fila_N`/`sector_N`/base-cuota shapes, and a "result casilla" designation.
  Sections that are all not-applicable should collapse with a sentence. Please treat non-numeric
  `number` values (B18) as label-only rows.
- B (casilla row): the row must show number, official label, formatted value, origin glyph + word and a
  help affordance within 78 usable columns at 80x24; missing is "—" + word, proven zero is a formatted
  zero. Use the state vocabulary table in 2.7 so all lenses speak the same words.
- C (editing): the stepper's Rellenar/Calcular steps need required-missing counts, manual vs imported
  origin and a stale-since-last-calculation flag; edits must preserve earlier values (B16) or the stepper
  lies. Save per casilla from the edit modal, like the profile manager; "Aplicar valores declarados" goes.
- D (imports / bindings): the Preparar step shows the import/readiness checklist with actions; an
  override must show "Cambiada por ti" plus the record value it replaced, and be revertible (removal is
  refused today). Provenance becomes the "De dónde sale" part of the help card.

## Sources

- `src/cadrumo/application/modelo/_edit_execution.py:102`
- `src/cadrumo/application/modelo/_work_review_assembly.py:193-196`
- `src/cadrumo/application/modelo/work_review.py`
- `src/cadrumo/application/workbench_generation.py:828`
- `src/cadrumo/entrypoints/tui/declarations/overview.py:60-64`
- `src/cadrumo/entrypoints/tui/declarations/overview.py:84-97`
- `src/cadrumo/entrypoints/tui/launcher.py:416`
- `src/cadrumo/entrypoints/tui/modelo/export_result.py`

- `src/cadrumo/entrypoints/tui/operations/modal.py:119`
- `src/cadrumo/locales/en/application.yml:1159-1161`
