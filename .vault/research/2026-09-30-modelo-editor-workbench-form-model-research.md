---
tags:
  - '#research'
  - '#modelo-editor-workbench'
date: '2026-09-30'
modified: '2026-10-03'
body_schema: 'body-v2'
body_hash: 'sha256:13ff10f47e92a427ec65a19406ef466ec5bbb8aab19f2d4286250db4a721c64d'
related:
  - "[[2026-09-30-modelo-editor-workbench-reference]]"
---

# `modelo-editor-workbench` research: `Form layout, grouping and ordering`

How can every modelo revision's edit interface be derived programmatically from registry authority: its pages, sections, grids, order and headings, and the typed read model the TUI renders? The evidence favours a generated, declared layout per revision anchored in the official record designs over any runtime reading of section paths or declaration order. Measured on 2026-09-30 against the live tree and the published authority; probe scripts ran in session scratch and were not retained, so every figure names the code or data it was measured from.

## Findings

Investigator: lens A. Date: 2026-09-30. Scope: how every modelo revision's edit interface is
derived from registry authority. That covers pages, sections, rows/grids, repeated groups, order,
headings, required/applicability, and the typed application read model the TUI renders.

#### 0. Method and provenance of numbers

- **Authority measured.** This worktree has no packaged descriptor, so the published authority at
  `.authority/` was copied read-only to scratch and loaded through the canonical reader. The loader
  was `bundled_indexed_authority().operation()`, then `revision_ids()`,
  `revision_with_export_layouts()` and `derive_export_layouts_from_bindings()`
  (`src/cadrumo/domain/calculations/registry/export.py:91`). The descriptor's logical generation is
  `a18d71b0…`, published 2026-09-29 21:10.
- **Hydration.** Every figure is **hydrated** (after delta materialisation), not authored rows.
  The population is 58 modelos, **146 revisions and 31,415 casillas**. The 2026-09-30 reference
  reported 13,046 authored rows, and the 2026-09-07 reference reported 128/29,678 on an older tree.
- **Official design text.** This was read from the extracted record-design sidecars
  (`src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_*/files/*.extracted.md`). Each
  sidecar was selected through the revision's own `record_design` source refs, so there is no
  cross-edition borrowing. Modelo 100 was read from the RentaWeb `.properties` dictionaries and the
  2025 XSD.
- **Probe scripts.** All probes are under (session scratch, not retained):
  - `p1_census.py`: census.
  - `p2_design_join.py` and `p3_offset_join.py`: design joins.
  - `p4_seed.py`, `p5_render.py` and `p6_rows.py`: a working prototype of a modelo-independent
    layout seed over all 146 revisions.
  - `a*.py`: analyses.
- **Scratch reader.** The scratch copy `rdreader.py` keys records by the full `#` heading; see bug B3.
- **Repository.** Nothing under `Y:\` was written. Git was not called.

---

#### 1. Findings

##### F1. The registry section path cannot be used unaided as the form's grouping

- **Depth and token counts.** Every casilla declares `section`
  (`src/cadrumo/domain/calculations/registry/schema_surfaces.py:342`). Hydrated depths are:
  1 → 3,251; 2 → 13,439; 3 → 14,099; 4 → 260; 5 → 366. There are 1,451 distinct tokens and 1,725
  distinct paths. No token has a catalogue heading.
- **Inconsistent granularity across modelos.**
  - 303/2025 has 72 leaf sections for 219 casillas, and 62 of those leaves hold a single casilla.
    Row indices and even column names are encoded as path segments, for example
    `iva/prorrata/actividad/fila_3/operaciones_total` and
    `iva/deducciones/sectores_diferenciados/sector_1/domestic_current_base`. The last of these uses
    English tokens inside a Spanish taxonomy.
  - 390/2025 has only 15 leaves, one of which (`iva/anual/deducible`) holds 156 casillas.
  - 200/2025 has 708 leaves, 173 of them singletons.
  - 100/2025 has 169 leaves. Its tokens are the XSD element names snake-cased
    (`deduccion_autonomica_res`).
- **The top segment is not a page.** 33 of 146 revisions have a single first token (for example
  390 = `iva`, and 303 is effectively all `iva`), so the top segment carries no page information.
- **Tokens are mostly modelo-local and often machine-shaped.**
  - Only 69 of 1,451 tokens occur in more than one modelo; `declarante` appears in 37 modelos,
    `liquidacion` in 17 and `resultado` in 11.
  - 386 tokens are longer than 40 characters, mangled from design text. Examples are 151's
    `cuota_correspondien_eneral_del_ahorro` and `gastos_de_aprovisio_s_y_de_suministros`, and
    200's `2015_inversiones_en_territ_africa_occidental_y_gas`.
- **Index tokens do not reliably mark rows.** 2,410 casillas carry an indexed token below the root.
  Only some of these are real row indices (`fila_N`, `sector_N`, `representante_N`,
  `descendiente_N`). In 151, `tipo_de_renta_1` … `_7` are design ordinals, and in 200 the numbered
  tokens are years.

##### F2. Snapshot and declaration order is not form order (measured)

- **Correlation with the official order.** Spearman ρ between snapshot position and export position
  (record order, offset) is:
  - 303: −0.06 to 0.08 across all six revisions.
  - 390/2025: 0.03.
  - 714: −0.50.
  - 111, 115 and 130: 1.0.
- **Concrete case.** In 303/2025 the snapshot opens with casilla **23**; casilla **01** is at index
  174 and the new-rate rows 150–158 are at 201–209. Section runs in snapshot order number 87 against
  72 distinct paths, so sections are also fragmented.
- **Consumers still rely on the order.**
  - `build_modelo_work_review_casillas` documents rows as coming back "in the snapshot's own casilla
    order, which is the registry's section order and casilla numbering"
    (`src/cadrumo/application/modelo/work_review.py:239`). That claim is false (bug B1).
  - The static inspection admission sorts casillas **lexically**
    (`src/cadrumo/application/modelo/workspace.py:1112`), so `108` precedes `11` (bug B2).

##### F3. Casilla-number order is a partial proxy and fails where it matters

- **Correlation with the export order.** Spearman ρ between numeric `number` and export order is:
  - 1.0 for 111, 115 and 130.
  - 0.83–0.99 for 303: rows 150–158 and 165–170 sit before 01 on the printed form, and
    120/122/123 sit before 62.
  - **−0.25 for 390/2024–2025**: the form runs 700/701, 667/668, 01/02, 702/703 …
  - 0.42 for 714.
- **Many casillas have no numeric box number.** 4,939 casillas (15.7%) carry a non-numeric
  `number`, which is a slug equal to the id. For example, the official 303/2025 box **[46]** is
  modelled only as `iva.resultado-regimen-general`, and no casilla carries number `46` (bug B5).
- **Other signals are thin.** `form_number` is set on 144 casillas only. `aliases` are
  label-variants, not positions, and set on 0 (`schema_surfaces.py:109`, `:418`).

##### F4. Export offsets are exact but partial

- **Coverage.** Fixed-width export fields place 11,982 casillas (38.1%), plus 478 through record
  `row_field_casilla_ids`. 1,061 casillas are placed at more than one export field.
- **Where offsets are absent.**
  - Modelo 100 has none (xml_dictionary).
  - 200/2024 has none.
  - 036 and 220 have none. They are placed only through the design number join.

##### F5. The official record-design corpus carries the form's real headings

- **Joinability.** The official description column is joinable in two ways:
  - By (design record, offset): 9,523 casillas (30.3%). The registry record id (`m303-declaration`)
    is not the design identity (`DP30301`), so the design record was chosen by best offset/length
    match (≥60%).
  - By the `[NN]` box number in the text: 14,507 casillas (46.2%).
  - Union: 15,634 (49.8%).
  - Per-modelo union: 111 100%, 130 95%, 303 81%, 390 90% (372/414 in 2025), 200 100%, 220 91%,
    490 87%, 714 77%.
- **The descriptions are hierarchical headings joined by " - ".** For example,
  `sidecar 06-303-ejercicio-2025…extracted.md:67–73` reads
  `Liquidación (3) - Regimen General - IVA Devengado - Régimen general - Base imponible [01]`.
  That is apartado > block > sub-block > row > column, with the box number included. Further
  examples:
  - 111: `Rendim. del trabajo - Rendimientos dinerarios - Nº de perceptores`.
  - 390: `5. Operaciones Reg. Gral. - Base Imponible y cuota - Reg. ordin. - Tipo 21% - Cuota [06]`.
  - 130: `Liquidación (3). I. Actividades econ. Estim. Directa - [01] Ingresos computables…`. This one
    uses a different separator style.
- **Page boundaries are official.** Design records (`DP30301` … `DP30305`, `Pág. 2 bis`) are the
  printed pages. The design text also states page conditions, for example "En el caso de un sujeto
  pasivo de IVA para el que no aplique el régimen simplificado, esta página 2 no debe incluirse".

##### F6. Modelo 100 has a second official seed with near-total coverage

- **Join coverage.** Joining casilla `number` to the RentaWeb dictionary box (exact 4-digit box
  only; identification boxes use `*NN`) places 2,205 of 2,249 casillas (98.0%) in 2025 and 1,531 of
  1,531 (100%) in 2020. This gives a 240-node element tree.
- **The runtime already reads these paths.** The same dictionary paths are read at runtime as
  `official_reference` (`src/cadrumo/application/modelo/_work_review_assembly.py:206`).
- **The XSD gives order and cardinality.** It declares order through `xs:sequence` and repeat
  cardinality through `maxOccurs`:
  - 69 elements have `maxOccurs` > 1.
  - Examples are `Inmueble` ≤180, `Hijo` ≤15 and `ActividadEstDirecta` ≤6.
- **Headings are not available.** The XSD carries only 110 `documentation` nodes, so element names
  (`RdtoCapitalMobiliario`) are not headings and 100's headings must be authored.
- **Structural gap.** The registry models each XSD-repeatable block as one slot of scalar casillas.
  For example, 128 casillas sit in `toma_datos_ampliada/inmuebles/inmueble` against an official
  cardinality of 180.

##### F7. The placement ladder: 94% of casillas have an official anchor

This measures the best available anchor per casilla, all revisions (`a11.py`, `p4_seed.py`):

| Anchor | Casillas | % |
|---|---:|---:|
| export offset (+ design description where joined) | 11,982 (+478 row ids) | 38.1 |
| RentaWeb dictionary path (modelo 100) | 11,272 | 35.9 |
| design `[NN]` only (no offset) | 6,111 | 19.5 |
| numeric casilla number only | 203 | 0.6 |
| working figure (slug, computed/bound/informational, not on form) | 708 | 2.3 |
| slug, manual, no official anchor | 1,141 | 3.6 |

- **Where the anchorless manual casillas sit.** They are concentrated in 036 (635), 220 (194) and
  303 (18 across revisions).
- **Where the working figures sit.** 303 has about 33 per revision, for example
  `iva.repercutido.general` and `iva.soportado.interiores.base` labelled "(parte de la casilla
  oficial 40)". 390 has about 34 per revision.
- **What a seed can reach.** A prototype seed placed 29,566 of 31,415 casillas (94.1%) with zero
  per-modelo code. The remaining 1,849 are explicitly unplaced with a reason.

##### F8. No declared per-casilla row signal exists; declared row sets do

- **Candidate signals on the casilla are all dead ends.**
  - `semantic_role` is set on 25,861, but echoes the number (`dr303_23`) on those measured.
  - `continuidad_id` (`dr303-23`) is continuity, not layout.
  - `aliases` = 0, and `form_number` = 144.
  - Nothing on a casilla says "I am the Cuota column of row X".
- **Repeated rows are declared at record level.** 34 export records repeat
  (`schema_exports.py:867`): 23 `binding_rows` and 11 `projection_rows`. They span 10 modelos
  (131, 180, 184, 190, 193, 296, 303 RS, 347, 349, 720). 19 records carry `row_field_casilla_ids`
  (`:869`), and bindings carry `row_grouping` on the row_set channel
  (`binding_value_contract.py:124`). These are open detail-row sets (perceptores, declarados,
  operadores), which are different from paper-form rows.
- **Heuristic row recognition from label stems works only as a seed.**
  - Registry `es` label "stem - column": 5,594 casillas in 1,853 rows.
  - Design description: 6,525 casillas in 2,050 rows.
  - Keeping only column signatures that repeat on the page: 5,042 casillas in 1,816 rows.
  - The top signatures are `base imponible|cuota` (486), `deducción pendiente|aplicado|pendiente`
    (165) and `base imponible|cuota deducible` (130). 5-column prorrata rows appear 50 times, and
    `base|tipo %|cuota` 38 times.
- **The heuristics fail visibly.**
  - 111's `especie-` has no space before the dash, so a row splits.
  - 200 turns a 25-line balance-sheet list into one "row".
  - Under the lax rule, 303 page 3 collapses "Información adicional" into one 6-column row.
- **Runtime label splitting is unsafe across locales.** The `" - "` count matches `es` in only
  9,870 of 10,287 `en` labels (96%); `ca` is 9,874 and `hu` 9,714. So row and column headers must
  be declared keys, not a runtime split of casilla labels.

##### F9. The 303 "Tipo %" boxes are editable but never filed

- **The mismatch.** In 303/2025, casillas 02, 05, 08, 17, 20, 23, 151 and 157 are `manual` `ratio`
  and therefore offered as writable (`edit_admission.py:134`). The export emits design literals at
  their slots instead:
  - offset 186 = `"00400"`, 264 = `"01000"` and 303 = `"02100"`, in record `m303-declaration`.
  - The design itself says `Constante "00400". Nota 7`.
- **Consequence.** An operator edit to these casillas can never reach the fichero, yet only 154,
  166 and 169 are export-addressed. The form needs a "fixed by the official design" cell state.
  See bug B4.

##### F10. There is no signal for "required", and "required-missing" needs a different source

- **The `required` flag is too sparse.** `required` (`schema_surfaces.py:344`) is set on 745
  casillas (2.4%):
  - 303/2025: `decl.ejercicio` and `decl.periodo` only.
  - 130: box 02 only, which is bound.
  - 111: none.
  - 100: 7 identification fields.
- **Export fields add nothing.** Export fields with `required=true` address **0** casillas in
  303, 130, 111, 390 or 200.
- **The completeness manifest is the usable denominator.** It is present in 86 of 146 revisions
  and covers 5,598 casillas. It is what `ModeloWorkProgress` measures against
  (`work_review.py:206`). Its coverage is:
  - 303/2025: 99 of 219.
  - 130: 20 of 20.
  - 111: 18 of 30.
  - 390/2025: 172 of 414.
  - 100/2025: 696 of 2,249.
- **Page-level applicability barely exists.** Optional export records number 43 of 455,
  `requires_positive_casilla_id` appears 3 times and record discriminators 12 times. The 80
  applicability rules are modelo-level obligations only.

##### F11. Help and label coverage (as the form will surface it)

- **Help counts are identical across the four locales.**
  - 303/2025: 92 of 219.
  - 130: 20 of 20.
  - **111: 0 of 30.**
  - 390/2025: 336 of 414.
  - 100/2025: 224 of 2,249.
  - 200/2025: 281 of 3,463.
- **The review label is Spanish only.** `ModeloWorkReviewCasilla.label` is `casilla.label`, the
  strict Spanish label (`_work_review_assembly.py:395`). The review carries no help text and no
  `required`.
- **Labels are otherwise healthy.** In the 5 revisions checked, labels with en == es number 0–2,
  so the earlier 26% untranslated figure no longer reproduces on these. The workspace label path
  now consults `casilla_localization_keys` (`workspace.py:1115`), so W03.P09.S39 appears addressed
  in source.

##### F12. The edit surface already knows writability, but not at form granularity

- **What admission projects.** Manual casillas become writable scalars. `MANUAL_INPUT` bindings
  become writable overrides. Everything else is read-only with one of three reasons
  (`edit_admission.py:134`, `edit_models.py:140`).
- **Most manual-input bindings are not attached to a casilla.** 8,014 bindings are `manual_input`
  and 7,969 of them are not any casilla's primary or alternate binding: 714 has 4,844, 369 has
  1,413 and 390 has 707. Only 45 bound casillas have a manual primary binding. The form must
  therefore place **binding inputs** as first-class fields, not only casillas.
- **Size.** The largest surface is 200/2025 with 3,474 entries, under the 4,096 cap
  (`edit_models.py:58`).
- **Missing distinctions.** Admission does not distinguish LOCK from CARRY sources. The accepted
  plan's W05.P17.S71 already notes this.

##### F13. What the TUI renders today

- **Overview.** It emits one bare `Input` per writable entry with the id as placeholder

- **Inputs page.** It groups by schema record family, not form section
  (`view/inputs.py:124`). Nothing consumes pages, sections, rows or order.
- **Profile editor.** It already has the fold/count/help language to reuse
  (`src/cadrumo/entrypoints/tui/profile/overview.py:155`).

---

#### 2. Proposed design

##### 2.1 Reconciling "every modelo, programmatically" with the accepted form-projection ADR

That ADR (`2026-09-07-tuimodelo-form-projection-adr`) protects six things:

- explicit data, not runtime inference;
- one runtime authority, compiled and validated with the revision;
- a closed placement axis with an unplaced-with-reason arm, so nothing is silently dropped;
- row groups declared, never flattened;
- a diffable stability gate;
- a source discriminator.

Its one clause that blocks the user's ask is "reviewed by a person before it ships", which leaves
revisions without a review as inspection-only.

**Recommendation: generate for all revisions, review to promote.** This needs an amendment to that
ADR, which is a costly decision, so it is flagged for the ADR owner.

- **Generate everywhere.** The development-time generator is modelo-independent: one seed ladder,
  no per-modelo code. It runs over **all** revisions in one pass. The prototype shows this is
  feasible today, placing 94.1% with official anchors.
- **Review becomes a declared field.** Each declaration carries
  `review: FormLayoutReview = GENERATED | REVIEWED(reviewer, date, notes)`.
- **GENERATED declarations ship and are editable.** They carry a visible, non-alarming disclosure:
  "Layout generated from the official record design; not yet reviewed". Editing is still addressed
  by casilla id or binding id, never by position, so a grouping defect can mislead the eye but can
  never mis-file a value. Mitigation: the box number is always shown.
- **REVIEWED is the promotion target.** Review is correction in the same format, as the ADR
  intends.
- **Inspection-only remains, but only as the generator-failure arm.** Examples are a revision whose
  anchors are ambiguous above a threshold, or a failed validator. It is no longer the default for
  unreviewed forms.
- **No runtime derivation of layout.** The runtime builder only joins the declared layout with
  live state. This keeps the ADR's rejection of option 1.

Everything else in that ADR stands. The stability gate becomes more valuable, because the
generator's output diff is the review queue.

##### 2.2 Two layers

- **Layout (declared registry family, domain).** It is per revision, generated, compiled and
  validated with the revision, and read only through the published authority. It answers: pages,
  sections, blocks (single fields, grids, repeated groups, binding-input groups), order, headings,
  placements, and page applicability hints.
- **Form state (application read model).** It is built per request from the layout plus
  `ModeloWorkReview` rows, the current `CalculationRevision`, the edit admission baseline and the
  locale. It answers: value, value state, editability, sources, help, progress counts and
  diagnostics.

##### 2.3 Declared layout family (domain) — `schema_form_layouts.py`

Proposed canonical module:
`src/cadrumo/domain/calculations/registry/schema_form_layouts.py`. It is enrolled in the registry
dispatch with a validator, and it is a new family under the existing revision loader and delta
machinery. It is authored in data at
`src/cadrumo/_data/registry/aeat/modelos/<m>/revisions/<r>/form_layout/*.toml`, generator-owned
and never hand-edited in place.

```python
class FormLayoutSeedSource(StrEnum):
    EXPORT_RECORD_DESIGN = "export_record_design"   # fixed-width offsets + design descriptions
    XML_DICTIONARY = "xml_dictionary"               # RentaWeb dictionary + XSD (modelo 100)
    DESIGN_BOX_NUMBER = "design_box_number"         # [NN] join without offsets (200/2024, 036, 220)
    CASILLA_NUMBER = "casilla_number"               # numeric order only, no official heading
    AUTHORED = "authored"                           # a reviewer moved/added it

class FormLayoutReviewState(StrEnum):
    GENERATED = "generated"
    REVIEWED = "reviewed"

class FormPlacementKind(StrEnum):
    ON_FORM = "on_form"              # primary official position
    WORKING_FIGURE = "working_figure"  # app-internal intermediate; shown under "Calculation details"
    UNPLACED = "unplaced"            # declared, with reason; never omitted

class FormUnplacedReason(StrEnum):
    NO_OFFICIAL_ANCHOR = "no_official_anchor"
    AMBIGUOUS_ANCHOR = "ambiguous_anchor"          # e.g. [NN] matches several design rows
    ANCHOR_CONFLICTS_WITH_SECTION = "anchor_conflicts_with_section"
    PENDING_REVIEW = "pending_review"

class FormCellKind(StrEnum):
    CASILLA = "casilla"
    BINDING_INPUT = "binding_input"
    DESIGN_CONSTANT = "design_constant"  # e.g. 303 Tipo % literal "00400"
    BLANK = "blank"                      # the paper form has no box here

class FormPageCondition(StrEnum):
    ALWAYS = "always"
    OPTIONAL_RECORD = "optional_record"                 # ExportRecordDefinition.required = False
    REQUIRES_POSITIVE_CASILLA = "requires_positive_casilla"
    PERIOD_RESTRICTED = "period_restricted"             # e.g. 303 page 4 "último periodo"
```

- **`FormLayoutDefinition`**: `id`, `revision_id`, `seed_source`, `review: FormLayoutReview`,
  `source_state_digest` (inputs: revision payload digest, design sidecar sha256s, generator
  version), `pages: tuple[FormPageDefinition, ...]`,
  `placements: tuple[FormPlacementDefinition, ...]`, `legal_refs`, `source_refs` (the record design
  or dictionary).
- **`FormPageDefinition`**: `id` (stable, e.g. `p1`), `official_ref` (e.g. `DP30301`,
  `Pág. 2 bis`, `TomaDatosAmpliada/RdtoTrabajo`), `heading_key`, `condition: FormPageCondition`,
  `condition_casilla_id: CasillaId | None`, `condition_periods: tuple[str, ...]`,
  `sections: tuple[FormSectionDefinition, ...]`.
- **`FormSectionDefinition`**: `id`, `heading_key`, `official_heading` (verbatim Spanish design
  text, e.g. `Liquidación (3) - Régimen general - IVA devengado`, kept for provenance and fallback),
  `blocks: tuple[FormBlockDefinition, ...]`. Nesting is not allowed; depth comes from `id` paths
  and is capped at 2 levels for a 24-row terminal.
- **Blocks**, as a discriminated union on `kind`:
  - `FormFieldBlock(kind="field", casilla_id | binding_id)`: a vertical label/value line.
  - `FormGridBlock(kind="grid", id, columns: tuple[FormGridColumn(key, heading_key)], rows: tuple[FormGridRow(key, heading_key, official_heading, cells: tuple[FormCell, ...])])`.
    Cells are positional against `columns`, and each is
    `FormCell(kind: FormCellKind, casilla_id | binding_id | constant_text)`. This declares the
    official paper "row" (base/tipo/cuota; nº perceptores/percepciones/retenciones; prorrata
    CNAE/…/%).
  - `FormRepeatingGroupBlock(kind="repeating", id, row_source: binding_id | export_record_id, min_rows, max_rows, columns: tuple[FormGridColumn, ...], column_casilla_ids)`:
    open detail-row sets. It never flattens rows into slot scalars, as the dual-keying ADR
    requires.
  - `FormBindingInputsBlock(kind="binding_inputs", binding_ids)`: manual-input bindings that no
    casilla owns (see F12).
- **`FormPlacementDefinition`**: `casilla_id`, `kind: FormPlacementKind`,
  `unplaced_reason: FormUnplacedReason | None`, `box_number: AeatBoxNumber | None`,
  `aliases: tuple[FormAliasPosition, ...]`.
  - `box_number` is the official printed number. It is taken from `number` when numeric, else from
    the design `[NN]`, which fixes F3's slug-numbered boxes such as 303 `[46]`.
  - An alias is another official position of the same box (1,061 multi-placed casillas). It is
    shown as "also appears at p3 · Resultado" and is never editable twice.

**Validator** (`FormLayoutValidator`, enrolled at the registry dispatch). It refuses a layout when
any of the following holds:

- a placement is missing for any casilla the revision defines;
- a placement or cell references an unknown casilla or binding;
- a casilla is ON_FORM in more than one cell;
- an ON_FORM casilla is not referenced by exactly one cell or field block;
- a grid row's cell count is not equal to its column count;
- a DESIGN_CONSTANT cell has no literal;
- a repeating group points to a non-row_set binding or a non-repeating record;
- `source_state_digest` is stale against the revision it describes.

**Catalogue keys** for headings: see §2.6.

##### 2.4 Application read model — `application/modelo/work_form.py`

This extends the accepted work review rather than creating a parallel read model. `ModeloWorkForm`
is built **from** a `ModeloWorkReview`, and every field embeds the review's own
`ModeloWorkReviewCasilla`, so values and provenance are never re-derived. The model uses typed
pydantic `STRICT_FROZEN_CONFIG`, bounded tuples and no Textual types.

```python
class ModeloFormLayoutProvenance(StrEnum):
    REVIEWED = "reviewed"          # declared + reviewed
    GENERATED = "generated"        # declared, generator output, disclosure shown
    INSPECTION_ONLY = "inspection_only"  # no usable declaration; read-only list, reason stated

class ModeloFormEditability(StrEnum):
    EDITABLE_VALUE = "editable_value"        # manual casilla, set/clear admitted
    EDITABLE_OVERRIDE = "editable_override"  # manual-input binding override admitted
    OVERRIDABLE_SOURCE = "overridable_source"  # CARRY-disposition source: override wins, disclosed
    LOCKED_SOURCE = "locked_source"          # LOCK disposition (ledger/invoices/347/...): fix at source
    CALCULATED = "calculated"                # formula
    DESIGN_CONSTANT = "design_constant"      # fixed by the official design (F9)
    INFORMATIONAL = "informational"          # identification/period etc.
    UNSUPPORTED_KIND = "unsupported_kind"    # declared refusal view, never a text box
    NO_BASELINE = "no_baseline"              # admission absent/stale/refused; reason carried

class ModeloFormValueState(StrEnum):
    NEEDS_INPUT = "needs_input"      # manifest member ∧ writable ∧ no value ∧ not absent-by-design
    EMPTY = "empty"                  # optional and empty
    ENTERED = "entered"              # operator value present in revision.input_values_by_casilla_id
    OVERRIDDEN = "overridden"        # binding override present, or OPERATOR_OVERRIDE anomaly
    IMPORTED = "imported"            # resolved binding from a non-manual source (ledger, profile, borrador…)
    CALCULATED = "calculated"
    PROVEN_ZERO = "proven_zero"      # absent_by_design — never shown as a plain 0
    BLOCKED = "blocked"              # blocked_by non-empty / BROKEN_CALCULATION_CHAIN
    STALE = "stale"                  # value predates an uncalculated edit (from lens C's session)

class ModeloFormBoxNumberKind(StrEnum):
    OFFICIAL = "official"            # printed box number
    RECORD_FIELD = "record_field"    # informative modelos (347/190…): record position, no box
    NONE = "none"                    # working figure
```

- **`ModeloFormField`**:
  - `address: ModeloFormFieldAddress`, a casilla or binding. This is the semantic address that D2
    requires.
  - `review: ModeloWorkReviewCasilla | None`, which is `None` for pure binding inputs.
  - `box: ModeloFormBoxNumber(kind, text)`.
  - `label: ModeloWorkspaceLocalizedTextV1 | ModeloWorkspaceTechnicalLabelV1`, reusing the
    existing fallback disclosure types.
  - `help: ModeloWorkspaceLocalizedTextV1 | None`.
  - `column_key: str | None`, set when the field sits in a grid.
  - `presentation_kind`, from the D2 closed set.
  - `editability: ModeloFormEditability`, `value_state: ModeloFormValueState`.
  - `source_kinds: tuple[BindingSourceKind, ...]`.
  - `manifest_member: bool`, `declared_required: bool`.
  - `constraints_disposition: DECLARED | UNDECLARED`.
  - `aliases: tuple[ModeloFormAliasRef, ...]`.
  - `design_constant: str | None`.
- **`ModeloFormGridRow`**: `key`, `heading`, and
  `cells: tuple[ModeloFormField | ModeloFormConstantCell | ModeloFormBlankCell, ...]`.
- **`ModeloFormGrid`**: `id`, `columns: tuple[ModeloFormColumn(key, heading)]`, `rows`.
- **`ModeloFormRepeatingGroup`**: `id`, `row_source`, `cardinality(min, max)`, `columns`, a page of
  `rows` with stable row addresses, and `cursor`. It follows the D3 paging rule.
- **`ModeloFormSection`**: `id`, `heading`, `official_heading: str | None`, `blocks`, and
  `counts: ModeloFormCounts`. The counts are total, needs_input, entered, imported, calculated,
  overridden, blocked and proven_zero.
- **`ModeloFormPage`**: `id`, `heading`, `official_ref`, `condition`,
  `condition_met: bool | None`, `counts` and `sections`.
- **`ModeloWorkForm`**:
  - Identity: `modelo`, `filing_year`, `period`, `registry_revision_id`, `work_unit_id`,
    `calculation_revision_id`, `edit_baseline_id | None` and `layout_digest`.
  - Layout facts: `layout_provenance`, `seed_source`, `locale`.
  - Structure: `pages`, `working_figures: ModeloFormSection`,
    `unplaced: tuple[ModeloFormUnplacedEntry(casilla, reason)]`.
  - Measures: `coverage: ModeloFormCoverage(placed, working, unplaced, total)` and
    `progress: ModeloWorkProgress`, reusing the review's own.

**Model validator: the totality invariant.**

- Every `review.casillas[*].casilla_id` appears exactly once across ON_FORM fields,
  working_figures and unplaced.
- Every admission-writable address appears exactly once as a field.
- Any violation raises; nothing is silently dropped.

##### 2.5 Builder algorithms

**Runtime builder** `build_modelo_work_form(review, layout, snapshot, revision, baseline, locale)`.
It is pure and deterministic. It makes no ledger calls and does no registry interpretation beyond
typed reads.

1. Index the review rows by casilla id and the baseline's `permitted_surface` by address.
2. Choose the provenance:
   - `layout is None or not layout.valid_for(snapshot.revision)` → INSPECTION_ONLY. Emit one
     section listing review rows in box-number order, all read-only, with the reason.
   - Otherwise → REVIEWED or GENERATED, as declared.
3. For each page, section and block in declared order:
   - Resolve the heading through the catalogue key. Fall back to `official_heading` verbatim
     (Spanish), marked `fallback=official_spanish`. Fall back again to a technical label (§2.6).
   - For each cell or field, classify `editability` with this precedence:
     1. data-kind unsupported;
     2. DESIGN_CONSTANT;
     3. the baseline entry: writable scalar → EDITABLE_VALUE, writable binding → EDITABLE_OVERRIDE,
        non-writable with reason `computed_by_formula` → CALCULATED;
     4. the bound source's disposition on the LOCK/CARRY ladder → LOCKED_SOURCE or
        OVERRIDABLE_SOURCE;
     5. informational input kind → INFORMATIONAL;
     6. no baseline → NO_BASELINE.
   - Classify `value_state` with this precedence:
     1. `blocked_by` or BROKEN_CALCULATION_CHAIN → BLOCKED;
     2. `absent_by_design` → PROVEN_ZERO;
     3. OPERATOR_OVERRIDE, or a binding override present → OVERRIDDEN;
     4. `revision.input_values_by_casilla_id` has the id → ENTERED;
     5. realised COMPUTED → CALCULATED;
     6. a resolved binding from a non-manual source → IMPORTED;
     7. an empty value with `manifest_member` and writable → NEEDS_INPUT;
     8. otherwise EMPTY.
   - Attach help and localized labels using the casilla's localization key chain. Do not use
     `review.label`, which is Spanish only.
   - Roll counts up to section, then page, then form.
4. Place WORKING_FIGURE casillas in `working_figures`, in formula-dependency order and then by id.
5. Emit `unplaced` with reasons, and assert the totality invariant.
6. Page `condition_met` is evaluated from the facts that exist:
   - OPTIONAL_RECORD → None ("may not apply"), unless the page has any value.
   - REQUIRES_POSITIVE_CASILLA → the value of that casilla is > 0.
   - PERIOD_RESTRICTED → whether the period is in `condition_periods`.

Cost: O(casillas + bindings). 200/2025 has 3,474 entries. The builder is eager and complete, and
paging belongs to the renderer per D3.

**Development-time generator** the former source file. It is modelo-independent:
one seed ladder, the same code for all 146 revisions.

1. **Anchors.** Anchors are collected in this order:
   - (a) export field (record order, offset) joined to the design row, choosing the design record
     by the best offset/length match;
   - (b) the XML dictionary line order and element path (100);
   - (c) the design `[NN]` match;
   - (d) the numeric casilla number;
   - (e) otherwise, working figure if non-manual, else unplaced with NO_OFFICIAL_ANCHOR.
   Multi-matches become aliases, with the lowest (record, offset) as primary. `[NN]` hits in more
   than one design row become AMBIGUOUS_ANCHOR unless the offset resolves them.
2. **Pages.** Pages are:
   - the design record (fixed width);
   - the third-level XSD element group (100), for example RdtoTrabajo, Inmuebles or
     DeduccionAutonomicaRes, rather than the useless DatosEconomicos/Resultados;
   - otherwise the first section token.
   Page conditions come from `ExportRecordDefinition.required`, `requires_positive_casilla_id` and
   the design notes. The notes are recorded as reviewer TODOs, never parsed as law.
3. **Sections.** Split the design description on dash-with-whitespace and strip `[NN]` and
   parenthesised formulas. The section is the longest common heading prefix of a contiguous run.
4. **Grids.**
   - Candidate rows are contiguous runs sharing a stem with distinct last segments.
   - Keep a run only when its column signature matches the reviewed column vocabulary (§2.6) or
     repeats on the same page.
   - Adjacent kept rows with identical signatures merge into one `FormGridBlock`.
   - Missing cells, such as 303's Tipo % slots bound to literals, become DESIGN_CONSTANT with the
     literal. Absent slots become BLANK.
   - Measured yield: 5,042 casillas in 1,816 rows under the strict rule.
5. **Repeating groups.** These come from `ExportRecordRepeat` records, `row_grouping` bindings and
   XSD `maxOccurs` > 1 for 100.
6. **Binding inputs.** Manual-input bindings without an owning casilla go to a
   `FormBindingInputsBlock` in the section of their export record, or else a "Other inputs"
   section.
7. **Emit the output.** Write TOML plus a review worksheet. The worksheet diffs against the
   predecessor revision's declaration via `continuidad_id`, so placements inherit across editions
   and the delta machinery keeps it compact. The stability gate fails on a moved placement without
   an acknowledgement.

##### 2.6 Heading strategy (es / en / ca / hu)

| Option | Measured cost and value | Verdict |
|---|---|---|
| Shared keys per section token (`modelo.section.<token>`) | Only 69 of 1,451 tokens are shared. The same token (`resultado`, `totales`) means different blocks in different modelos. 386 tokens are machine slugs. Keys would enshrine the wrong tree (F1). | Reject |
| Per-modelo keys over the registry section tree | 2,098 prefix nodes (303: 86, 390: 20, 100: 223, 200: 855) × 4 locales. Encodes 303's over-fragmentation and 390's under-fragmentation. | Reject as primary |
| Official design headings, verbatim | Real, legally named text. Joined for about 50% overall, 98% for 100 via paths (but no human text there). Spanish only, with abbreviations such as "Reg. Gral." and "Rendim." | Use as **seed and provenance**, and as a disclosed fallback |
| Humanized token fallback (`regimen_general` → "Regimen general") | Cheap, but wrong accents, English tokens in 303, and 40+ character mangled tokens. Reads as authoritative when it is not. | Reject for the operator UI. Keep only the technical-label fallback with disclosure, as today |

**Recommended key scheme.** Headings are declared keys of the layout family, living in the existing
per-modelo schema catalogues:

- **Page and section headings.**
  `modelo.schema.<m>.form.<node_key>.heading`, plus optional `.help`. `node_key` is stable across
  revisions (for example `p1.liquidacion.devengado`) so the continuity-style reuse the catalogue
  already practises applies. A new key is created only when legal meaning changes, per the locale
  rule.
- **Grid column headings.** A small **shared** vocabulary, because the legal meaning is identical
  across modelos: `modelo.form.column.base_imponible`, `.tipo`, `.cuota`, `.cuota_deducible`,
  `.numero_perceptores`, `.importe_percepciones`, `.importe_retenciones`,
  `.valor_percepciones_especie`, `.ingresos_a_cuenta`, `.aumentos`, `.disminuciones`,
  `.pendiente_inicio`, `.aplicado`, `.pendiente_futuro`, and so on. The top 12 measured signatures
  cover most grid rows, so a vocabulary of about 30 keys covers the corpus's recurring grids.
- **Grid row headings.** These are per-modelo keys (`…form.<node_key>.row.<row_key>.heading`). They
  are seeded from the registry label stem, which is better than the design here. For example, the
  design says "Régimen general" for the 4%, 10% and 21% rows alike, while the registry says "tipo
  super-reducido 4pct".
- **Generation and translation.** The generator writes `es` from the design heading, lightly
  normalised, with the reviewer correcting it. `en`, `ca` and `hu` go through the canonical locale
  workflow, never by editing catalogues by hand.
- **Fallback order at runtime.**
  1. The locale key.
  2. The `es` key, disclosed as "Spanish". This reuses `ModeloWorkspaceLocaleDisposition`.
  3. `official_heading` verbatim, disclosed as "official Spanish text".
  4. The technical node id, disclosed as "technical" (`ModeloWorkspaceTechnicalLabelV1`).

  The builder never humanizes snake_case.
- **Estimated authoring load to reach REVIEWED.**
  - 303: about 25 section and row headings plus shared columns.
  - 130: 5.
  - 111: 8.
  - 390: about 60.
  - 100: about 240, and it has no official human text to seed from.
  - 200: about 500+.

  This matches the ADR's "smallest fixed-width modelos first" ordering.

##### 2.7 Mockups

The legend is shared with lens B, which owns the final glyphs:

- `=` calculated
- `⇣` imported (ledger, profile or borrador)
- `✎` you entered it
- `⚑` needs your input
- `◆` fixed by the official design
- `⤺` override of an imported value
- `0̸` proven zero, not applicable
- `…` empty and optional

Box numbers are always shown in brackets. The values are synthetic.

**303 · 2025 · 1T, page 1 (DP30301 "Liquidación") at 120×36.**

```
Modelo 303 · IVA · 2025 1T · Draft                          Calculated 12:04 · ⚑ 2 need input · ⤺ 1 override · layout: official design (generated)
 [1 Liquidación ⚑2]  2 Régimen simplificado (does not apply)  3 Resultado  4 Exonerados 390 (4T only)  5 Prorratas  │ Calculation details ▸
────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
▾ Régimen general · IVA devengado                                                          12 boxes · ⇣ 5 · ✎ 1 · ⚑ 1 · = 5
                                                    Base imponible            Tipo %                 Cuota
  General 21 %                               [07]   10.000,00 ⇣        [08]  21,00 ◆       [09]    2.100,00 =
  Reducido 10 %                              [04]      800,00 ⇣        [05]  10,00 ◆       [06]       80,00 =
  Superreducido 4 %                          [01]        …             [02]   4,00 ◆       [03]        0,00 =
  Tipo 2 % (desde 2024)                     [165]        …            [166]   0,00 ◆      [167]        0,00 =
  Adquisiciones intracomunitarias            [10]      300,00 ⇣                            [11]       63,00 =
  Otras op. con inversión del sujeto pasivo  [12]        ⚑                                 [13]        0,00 =
  Modificación bases y cuotas                [14]    -120,00 ✎                             [15]      -25,20 ✎
  Recargo de equivalencia 5,2 %              [22]        0̸             [23]   5,20 ◆       [24]        0̸
  … 4 more recargo rows (0̸)                                                                           ▸ show
  Total cuota devengada                                                                    [27]    2.217,80 =
▸ Régimen general · IVA deducible                                                         19 boxes · ⇣ 9 · = 6 · ⤺ 1
▸ Resultado del régimen general                                                                   [46]      1.105,30 =
────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
[12] Base imponible · Otras operaciones con inversión del sujeto pasivo (excepto adq. intracomunitarias)
Needs your input: this box is part of the declaration and no source filled it. Type the base; [13] is calculated.
What it is: … (casilla help)                      Source: manual entry          Legal: LIVA art. 84.Uno.2º
────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
←/→ page  ↑/↓ box  enter edit  o override  i import  ? help  / find box  n next ⚑  f filter: all│needs input│edited
```

**303 page 1 at 80×24.** Grids collapse to stacked rows: the row heading on one line and the cells
on the next, with column names inline. Group counts move to the fold line.

```
303 · 2025 1T · Draft · ⚑2 ⤺1               [1/5 Liquidación]
─────────────────────────────────────────────────────────────────
▾ IVA devengado            12 · ⇣5 ✎1 ⚑1
 General 21 %
   [07] Base 10.000,00⇣ [08] 21,00◆ [09] 2.100,00=
 Reducido 10 %
   [04] Base    800,00⇣ [05] 10,00◆ [06]    80,00=
 Superreducido 4 %
   [01] Base        …   [02]  4,00◆ [03]     0,00=
 Adquisiciones intracomunitarias
   [10] Base    300,00⇣              [11]    63,00=
 Otras op. inversión sujeto pasivo
   [12] Base        ⚑                [13]     0,00=
 Modificación bases y cuotas
   [14] Base   -120,00✎              [15]   -25,20✎
 … 5 recargo rows (0̸)                              ▸
 Total cuota devengada               [27] 2.217,80=
▸ IVA deducible            19 · ⇣9 =6 ⤺1
▸ Resultado régimen general          [46] 1.105,30=
─────────────────────────────────────────────────────────────────
[12] Needs input · ? help · enter edit
←→ page ↑↓ box ⏎ edit ? help n next⚑ / find
```

**130 · 2025 · 2T, the single page (design "DR 13001") at 120×36.**

```
Modelo 130 · IRPF pago fraccionado · 2025 2T · Draft                      Calculated 09:12 · ⚑ 1 need input · layout: official design (reviewed)
────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
▾ I. Actividades económicas en estimación directa                                        7 boxes · ⇣ 3 · ✎ 1 · = 3
  [01] Ingresos computables del ejercicio (acumulado)                                               24.000,00 ⇣ ledger
  [02] Gastos fiscalmente deducibles (acumulado)                                                     9.500,00 ⇣ ledger
  [03] Rendimiento neto  ([01] − [02])                                                              14.500,00 =
  [04] 20 % de [03]                                                                                  2.900,00 =
  [05] A deducir: pagos fraccionados de trimestres anteriores                                        1.200,00 ⇣ previous filing
  [06] A deducir: retenciones e ingresos a cuenta soportados                                           300,00 ✎
  [07] Pago fraccionado previo del trimestre  ([04] − [05] − [06])                                   1.400,00 =
▸ II. Actividades agrícolas, ganaderas, forestales y pesqueras                          4 boxes · all 0̸ (not applicable)
▾ III. Total liquidación                                                                  9 boxes · ⚑ 1 · = 7
  [12] Suma de pagos fraccionados del trimestre  ([07] + [11])                                       1.400,00 =
  [13] A deducir: minoración (art. 110.3 RIRPF)                                                        100,00 =
  [14] Diferencia  ([12] − [13])                                                                     1.300,00 =
  [15] A deducir: resultados negativos de trimestres anteriores                                          0,00 =
  [16] A deducir: deducción por vivienda habitual                                                        …
  [17] Total  ([14] − [15] − [16])                                                                   1.300,00 =
  [18] A deducir: resultado a ingresar de autoliquidaciones anteriores (solo complementaria)             ⚑
  [19] Resultado de la autoliquidación                                                               1.300,00 =
▸ Calculation details (1 working figure: saldo negativo trasladable)
────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
[18] Only if this is a complementaria: the amount you already paid for this period. Otherwise leave empty. ? more
```

**130 at 80×24.** Each field is a single line: box, a label truncated with an ellipsis, then the
value right-aligned with its state glyph. Section II stays folded when all of its boxes are 0̸. The
help band is one line.

```
130 · 2025 2T · Draft · ⚑1          layout: official
────────────────────────────────────────────────────
▾ I. Estimación directa        7 · ⇣3 ✎1 =3
 [01] Ingresos computables    24.000,00 ⇣
 [02] Gastos deducibles        9.500,00 ⇣
 [03] Rendimiento neto        14.500,00 =
 [04] 20 % de [03]             2.900,00 =
 [05] Pagos trim. anteriores   1.200,00 ⇣
 [06] Retenciones soportadas     300,00 ✎
 [07] Pago fraccionado previo  1.400,00 =
▸ II. Agrícolas…               4 · 0̸
▾ III. Total liquidación       9 · ⚑1 =7
 [12] Suma pagos fraccionados  1.400,00 =
 [13] Minoración art.110.3       100,00 =
 [14] Diferencia               1.300,00 =
 [15] Negativos trim. ant.         0,00 =
 [16] Deducción vivienda              …
 [17] Total                    1.300,00 =
 [18] Resultado anteriores            ⚑
 [19] Resultado                1.300,00 =
────────────────────────────────────────────────────
[18] Only for complementaria · ? help
```

These mockups show three things the model must supply:

- **Official apartado headings.** The 130 design gives I, II and III. The registry sections
  (`actividades_economicas_estimacion_directa`, … `resultado_final`) give 6 plus 1 and split III.
- **Formula-bearing labels.** The design already states `([01] - [02])`. Keep those as declared
  help or sub-labels, not by parsing at runtime.
- **Folding.** Folding a section whose every box is a proven zero is the biggest simplification
  lever on large forms.

---

#### 3. Suggestions ranked by user value vs effort

| # | Suggestion | Value | Effort |
|---|---|---|---|
| 1 | Build `ModeloWorkForm` over an **interim declared layout for 111, 115, 130 and 303** generated by the prototype ladder (offset + design). It ships with the GENERATED disclosure. These are the forms most operators file, and the data is 95–100% anchored. | Very high | M |
| 2 | Add `box_number` resolution (numeric number → design `[NN]` → none) and always render `[NN]`. This fixes 303 `[46]`, 390's slug boxes and 151/347 record fields. | High | S |
| 3 | Classify value state with NEEDS_INPUT from the completeness manifest, not `required`, with section, page and form rollups and "next ⚑" navigation. | High | S |
| 4 | Add the DESIGN_CONSTANT cell and editability for literal-exported rates (F9), so no edit is offered that cannot be filed. | High (correctness) | S |
| 5 | Declare grids (base/tipo/cuota, 111's three columns, prorrata) with the shared column vocabulary (about 30 keys × 4 locales). | High | M |
| 6 | Add the WORKING_FIGURE section ("Calculation details"), which moves about 33 app-internal 303 figures and about 34 in 390 off the official page without hiding them. | Medium-high | S |
| 7 | Amend the form-projection ADR to "generate for all, review to promote" (§2.1), run the generator over all 146 revisions, and publish coverage and stability gates. | High (unblocks every modelo) | M–L |
| 8 | Add binding-input blocks for the 7,969 casilla-less manual bindings (714, 369, 390). | Medium | M |
| 9 | Seed modelo 100 from dictionary line order and XSD `maxOccurs` row groups, and author about 240 headings. Add a CCAA page condition (482 autonómica casillas in 2025) so non-resident-CCAA pages fold. | Very high for 100 | L |
| 10 | Page conditions from optional records and design notes (303 page 2 RS and page 4 "último periodo"). | Medium | S–M |

---

#### 4. Bugs noted (not fixed)

- **B1.** `src/cadrumo/application/modelo/work_review.py:239` claims that the review rows are in
  "section order and casilla numbering". Measured: in 303/2025 box 23 comes first and box 01 is at
  index 174, and snapshot-vs-form ρ is about 0 for all six 303 revisions. Any consumer that trusts
  this order renders a scrambled form.
- **B2.** `src/cadrumo/application/modelo/workspace.py:1112` orders the static inspection with
  `sorted(inspection.casilla_ids)`, which is lexical: `108` sorts before `11`, and slug ids
  interleave.
- **B3.** `dev/registry/record_design_labels.py:50` uses `_RECORD_HEADING = r"^# (?P<record>\S+)"`,
  which truncates multi-word headings. In the 390 sidecar, "Pág. 0" through "Pág. 8" and
  "Pág. 2 bis" all collapse to the record key `Pág.`, and first-row-wins then returns the
  **wrong** design label for every page after the first. For example, `iva.anual.cuota-devengada-total`
  resolved to `[706] … Tipo 5% - Base imponible` instead of `[47] Total cuotas IVA`. Any
  label-borrowing tool built on this reader is wrong for multi-word record headings.
- **B4.** In 303/2025, casillas 02, 05, 08, 17, 20, 23, 151 and 157 are `manual` and admitted as
  writable, but their export slots are literals (`m303-2025.dp30301.f029` = `"00400"`, etc.). The
  operator can edit a value that is never filed. Box 154 is the only placed Tipo, and it is
  `computed`. This is a no-silent-under-declaration concern as well as a UI one.
- **B5.** The official 303/2025 box `[46]` has no casilla with `number` `46`. It exists only as the
  slug `iva.resultado-regimen-general`, whose `number` equals its id. Across the corpus, 4,939
  casillas have non-numeric numbers, and 273 of those have a design `[NN]` recoverable.
- **B6.** 303 section tokens mix English (`domestic_current_base`, `intra_eu_investment_cuota`)
  into the Spanish domain taxonomy, contrary to the naming rule. In 151, 200 and others, tokens are
  truncated or mangled design text (`cuota_correspondien_eneral_del_ahorro`).
- **B7.** The review label is Spanish only (`_work_review_assembly.py:395`). The review carries no
  help and no `required`, so any renderer built on the review alone cannot localise.
- **B8.** Modelo 111 has 0 of 30 help entries in every locale.
- **B9.** Modelo 100 repeatable XSD elements (`Inmueble` ≤180, `Hijo` ≤15, `ActividadEstDirecta`
  ≤6) are modelled as a single slot of scalar casillas. Only one instance is expressible. This is
  structural, and it may be deliberate, but it is undisclosed.
- **B10.** In the design joins, `[NN]` matches several design rows for 1,682 casillas in 200, 1,771
  in 220, 370 in 714 and 325 in 303. The `[NN]` join alone must not be used without an offset or
  reviewer tie-break.

#### 5. Risks and open questions

- **Q1.** The ADR amendment. Is GENERATED-and-editable acceptable to the ADR owner? The argument
  for it is address-by-id editing plus the always-visible box number. The argument against is that
  a misleading grid could invite wrong entries. Mitigation: GENERATED layouts render grids only
  when the column vocabulary matched, and otherwise as a vertical list.
- **Q2.** Where the layout lives. A registry family compiled into authority is the right place per
  the ADR. It needs a delta story, inheriting placements across editions by `continuidad_id`, or
  the corpus will duplicate 146 layouts.
- **Q3.** Headings for 100 and 200. There is no official human heading text for 100's XSD tree,
  and 200 has more than 850 section nodes. The review cost is real; GENERATED with the technical or
  official-Spanish fallback is the honest interim.
- **Q4.** Page applicability is mostly undeclared. Design notes state conditions in prose
  ("esta página 2 no debe incluirse…"). Encoding them as typed page conditions is legal-grounding
  work and needs citations. Do not infer them.
- **Q5.** Detail-row groups (347, 190, 349) versus fixed-slot grids (303 prorrata fila 1–5) are
  different kinds. Both must be modelled, and neither may flatten into the other.
- **Q6.** Lock and carry editability depends on the source-mesh disposition ladder
  (`application/aggregation/_source_mesh.py`). The builder must consume that same table, not a
  copy.
- **Q7.** Re-measure the design join after B3 is fixed in the dev reader. The figures here used a
  corrected scratch copy.
- **Q8.** The measured generation (`a18d71b0…`, a byte copy of `Y:\…\tui\.authority`) is the one
  the coordinator verified as current on 2026-09-30. Re-run the probes if it is republished before
  any gate threshold is set.

#### 6. Overlap notes for the other lenses

- **Lens B (casilla row widget).**
  - Render from `ModeloFormField`: `box`, `label` (with disclosure), `help`, `value`,
    `value_state`, `editability`, `source_kinds`, `aliases` and `design_constant`.
  - Grid rows need a 3–5 column cell layout with column headers from `ModeloFormColumn`.
  - At 80 columns, fall back to the stacked row form (§2.7).
  - Proven zero (0̸) must be visually distinct from an entered 0.
  - The `[NN]` box is always visible, even in grids.
- **Lens C (edit interaction).**
  - Editability arrives pre-classified: EDITABLE_VALUE, EDITABLE_OVERRIDE, OVERRIDABLE_SOURCE,
    LOCKED_SOURCE, DESIGN_CONSTANT, UNSUPPORTED_KIND and NO_BASELINE.
  - Addresses are semantic (casilla or binding), never grid positions.
  - Aliases must edit once.
  - The STALE value state is lens C's to set from the edit session. The form carries the slot.
  - The admission baseline's five-minute life means the form must be rebuildable without the
    baseline (NO_BASELINE), with editability re-attached when a fresh baseline is admitted.
- **Lens D (imports and bindings).**
  - The form supplies `source_kinds`, the IMPORTED and OVERRIDDEN states, and
    `FormBindingInputsBlock` for the 7,969 casilla-less manual bindings.
  - It supplies `FormRepeatingGroupBlock` for row_set bindings and repeating records (10 modelos).
  - "Imported from borrador" can use `revision.bindings_sourced_from_borrador`
    (`calculation_revision.py:188`).
- **Lens E (whole flow).**
  - The form is one destination: pages are the in-destination tab strip, and "Calculation details"
    (working figures plus the unplaced list) is a secondary pane, not a page.
  - The coverage figure (placed, working and unplaced) and the layout provenance disclosure belong
    in the destination header.
  - The inspection-only arm is a distinct, honest screen state.
  - Progress (⚑ count, next ⚑) is the natural bridge to calculate and verify.

## Sources

- `dev/registry/record_design_labels.py:50`
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_*/files/*.extracted.md`
- `src/cadrumo/_data/registry/aeat/modelos/<m>/revisions/<r>/form_layout/*.toml`
- `src/cadrumo/application/modelo/_work_review_assembly.py:206`
- `src/cadrumo/application/modelo/work_review.py:239`
- `src/cadrumo/application/modelo/workspace.py:1112`
- `src/cadrumo/domain/calculations/registry/export.py:91`
- `src/cadrumo/domain/calculations/registry/schema_form_layouts.py`
- `src/cadrumo/domain/calculations/registry/schema_surfaces.py:342`

- `src/cadrumo/entrypoints/tui/profile/overview.py:155`
