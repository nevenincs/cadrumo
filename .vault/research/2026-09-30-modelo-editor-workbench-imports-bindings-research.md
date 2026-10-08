---
tags:
  - '#research'
  - '#modelo-editor-workbench'
date: '2026-09-30'
modified: '2026-10-03'
body_schema: 'body-v2'
body_hash: 'sha256:ac7f800bf245349bb270e26dae0f3f3fe105ef763d7fc6b08645d5880e15faed'
related:
  - "[[2026-09-30-modelo-editor-workbench-reference]]"
---

# `modelo-editor-workbench` research: `Imports, bindings, provenance and overrides`

Where does each casilla value come from, how does a person bring values in, and how are imported values overridden or restored? The evidence shows the everyday modelos expose no writable bindings, override policy is undeclared for half the source kinds, and provenance is misattributed for carries; it favours a schema-driven Sources hub keyed by a total source-kind policy table. Measured on 2026-09-30 against the live tree and the published authority; probe scripts ran in session scratch and were not retained, so every figure names the code or data it was measured from.

## Findings

Design spec for the Cadrumo TUI modelo editor workbench. It covers how a person sees where each
value comes from, brings values in from sources, and edits or overrides values that were imported.
Measured on 2026-09-30 against the live tree at `Y:\code\cadrumo-worktrees\tui`, branch
`feature/tui`, which had uncommitted edits to `work_review.py`; the tree was read as it stood.
Every file under `Y:\` was treated as read-only.

How it was measured: this worktree has no published authority descriptor. The loader refused with
`AuthorityDescriptorUnavailableError` at `src/cadrumo/domain/calculations/registry/authority.py:969`.
So the registry census compiles the authored tree in memory through
`dev.registry.compiler.authority.compile_structural_authority`, using the canonical loader and
hydrator. It takes the latest revision of each modelo and does not publish anything. The scripts
are in (session scratch, not retained) (`census.py`, `census2.py`, `srccas.py`, `proto_panel.py`,
`surface.py`, `manual.py`). Semantic search was not used; code was found with targeted grep and two
read-only exploration passes.

---

#### 1. Findings

##### 1.1 The source vocabulary the schema already has

A casilla gets a value from a source through a registry **binding**
(`BindingDefinition`, `src/cadrumo/domain/calculations/registry/schema.py:263`). Each binding carries
the following:

- `provider`: a discriminated union whose tag is the `BindingSourceKind`.
- `value`: a typed channel. The channels are decimal, integer, boolean, text, date, enum and row_set
  (`binding_value_contract.py:74`).
- `aggregation`: copy, sum, rows, count_distinct and so on.
- `applicability`, `terminal_origins` and `aeat_prefilled`.
- `legal_refs` and `source_refs`.

**A binding has no label, help text or catalogue key.** Its only human-facing handle is its id,
for example `modelo-390.page_7.prorratas-1-codigo-cnae`.

`BindingSourceKind` (`src/cadrumo/core/aggregation.py:226`) has 33 members. Three typed axes
already classify them:

| Axis | Where | Values |
|---|---|---|
| Provider disposition | `BINDING_PROVIDER_REGISTRATIONS[kind].disposition` | `filing_grade` (22 kinds), `deferred` (7: donativo_donor, gasto193_contributor, ledger_transaction, purchase_invoice_evidence, refund_operation, related_party_operation, withholding296), `non_runtime` (manual_input, design_constant). `borrador` and `iva_wallet_decision` are mesh-only. |
| Caller-override disposition | `CALLER_OVERRIDE_PRECEDENCE_LADDER`, `src/cadrumo/application/aggregation/source_mesh.py:390` | `LOCK` (12 kinds: ledger, invoice, M347, inventory, M303 annual summary), `CARRY` (4: previous_filing, relation_prefill, iva_compensation_annual_partition, prorrata_regularizacion). **The other 17 kinds are unclassified**, including profile, retenciones_aggregation, withholding, bienes_inversion_regularizacion, borrador and iva_wallet_decision (measured). |
| Plain-language wording | `src/cadrumo/locales/*/docs.yml` `docs.casilla.binding_source.*` ("from your IVA ledger entries") and `flows.yml` `flows.modelo_review.filter.option.binding_source.*` ("VAT ledger totals") | All 33 kinds are present in en. Today only the docs generator reads them. |

Sources are merged by precedence, with later tiers winning: profile, then the source-mesh backend,
then borrador, then caller (`src/cadrumo/application/modelo/calculation_resolution.py:139-180`).

Whether a caller may override a value is decided in two places:

- **At preparation**, against the static LOCK set (`calculation_actions.py:1279`).
- **After resolution**, against "every source the resolver actually owned in this calculation,
  minus CARRY" (`calculation_actions.py:1349-1354`, with the refusal at `:1940`). For
  retenciones_aggregation, withholding, foreign_asset and atribucion_member, the effective policy is
  therefore "locked, but only known at run time".

Modelo 303 casilla 110 has one more gate. Its carry must equal the IVA-wallet decision
(`iva_wallet_gate.py:448`, `:536-556`), and it can only be overridden through
`modelo iva-wallet override --reason --evidence-locator --confirm`. That is the one existing
override-with-reason precedent (`src/cadrumo/entrypoints/cli/_modelo_iva_wallet_cli.py:209`).

##### 1.2 Per-modelo source census

The census uses the latest revision of each modelo, compiled from the authored registry.
"Feeds casilla" counts bindings named by a BOUND casilla, either as primary or alternate.
"Formula-only" means a formula reads the binding but no casilla names it. "Fichero-only" means only
an export record field consumes it. "Nothing" means no consumer at all
(`binding_targets.binding_consumers`, `binding_targets.py:87`).

| Modelo (revision) | Casillas: manual / bound / computed / other | Bindings | By source kind | Feeds casilla / formula-only / fichero-only / nothing | manual_input bindings (the only TUI-writable ones) | Override policy: lock / carry / unclassified / enter |
|---|---|---|---|---|---|---|
| 303 (2026-y-siguientes) | 72 / 52 / 33 / 63 (61 projection-only) | 52 | ledger_iva_aggregation 47, profile 2, previous_filing 1, bienes_inversion 1, prorrata 1 | 52 / 0 / 0 / 0 | **0** | 47 / 2 / 3 / 0 |
| 130 (2019-y-siguientes) | 5 / 3 / 12 / 0 | 8 | ledger_renta_income 4, previous_filing 3, ledger_renta_gastos_pago_fraccionado 1 | 3 / 2 / 0 / **3** | **0** | 5 / 3 / 0 / 0 |
| 111 (2019-y-siguientes) | 19 / 9 / 2 / 0 | 9 | retenciones_aggregation 9 | 9 / 0 / 0 / 0 | **0** | 0 / 0 / **9** / 0 |
| 115 (2019-y-siguientes) | 1 / 2 / 2 / 0 | 2 | retenciones_aggregation 2 | 2 / 0 / 0 / 0 | **0** | 0 / 0 / **2** / 0 |
| 390 (2025) | 241 / 152 / 19 / 2 | 325 | manual_input 173, ledger_iva_aggregation 131, m303_simplificado_summary 10, relation_prefill 6, iva_comp_annual_partition 3, prorrata 1, bienes_inversion 1 | 152 / 0 / **173** / 0 | **173** (all fichero-only) | 141 / 10 / 1 / 173 |
| 347 (2025-y-siguientes) | 43 / 0 / 0 / 2 | 11 | m347_third_party_operation 11 (9 row_set) | 0 / 0 / 9 / **2** | **0** | 11 / 0 / 0 / 0 |
| 100 (2025) | 1,979 / 52 / 216 / 2 | 71 | profile 43, ledger_renta_gastos_ED 14, relation_prefill 7, inventory 3, manual_input 2, previous_filing 1, ledger_renta_income 1 | 55 / **16** / 0 / 0 | **2** (1 alternate for 0596, 1 boolean formula operand) | 18 / 8 / **43** / 2 |

Across the registry (latest revisions, 58 modelos) there are 10,388 casillas, of which 303 are bound
with a primary binding, and 3,100 bindings. 2,521 bindings (81%) are `manual_input`, and they are
concentrated in nine modelos:

| Modelo | manual_input bindings |
|---|---|
| 714 | 971 |
| 369 | 825 |
| 232 | 185 |
| 390 | 173 |
| 360 | 146 |
| 131 | 97 |
| 353 | 83 |
| 720 | 39 |
| 100 | 2 |

Almost all of them are fichero record fields that no casilla names. `aeat_prefilled` is set on 2 of
the 3,100 bindings, both in M100.

**What this means for the design:**

- For the everyday modelos (303, 130, 111, 115, 347), **the edit admission exposes zero writable
  bindings**. Every imported value is read-only in the TUI.
  - 303's 47 bindings are locked to the ledger.
  - 111 and 115 have no declared override policy.
  - The carries (303 casilla 110, 130 casilla 05 and the carries read only by formulas) can be
    overridden from the CLI but not from the TUI.
- **The only "binding override" inputs the TUI ever shows are M390 fichero fields.** They are
  rendered with raw ids as placeholders .
- A Sources view that lists only casilla-fed bindings would miss things. It would not show 130's two
  formula-only carries (the prior-year negative-results cap and the previous-year net income), M100's
  16 formula-only bindings, including the 130/131 pagos fraccionados relations, or M390's 173
  fichero-only fields.

##### 1.3 Runtime provenance the revision already persists

On a `CalculationRevision` (`src/cadrumo/domain/modelos/calculation_revision.py:803-905`):

- **`binding_overrides`**: despite the name, this is the replay map of **every resolved binding
  from every tier**, not only operator overrides (`calculation_resolution.py:335-342`).
  `input_values_by_casilla_id` is likewise a merged set: backend, bound, caller and profile-text
  values (`calculation_actions.py:526-560`).
- **`source_provenance`**: a tuple of `CalculationSourceRef` with resolver id, source kind, lineage
  role, `source_ref` (a stringly-typed `kind:id` such as `transaction:{id}`, `invoice:{id}`,
  `perceptor:{nif}`, `borrador:{snapshot}:binding:{id}` or `bienes-inversion-register:{year}`),
  fingerprint, `source_casilla_ids` and source filing year. **It carries no binding id**
  (`source_mesh.py:673-704`). Ledger rows carry no casilla link at all (`modelo_bindings.py:505-514`).
- **`source_issues`**: 5 durable reasons, such as unrouted observation, IVA scope failure and
  withholding detail absent.
- **`observations`**: per-casilla `CasillaObservation`, with `absent_by_design`, legal and source refs.
- **`cleared_casilla_ids`**: explicit clears.
- `borrador_snapshot_id` and `bindings_sourced_from_borrador`.

Calculation-time diagnostics (`CalculationSourceDiagnostic`, `source_mesh.py:513`) have typed
`reason`, `binding_id`, `relation_id`, `message` and `remedy` fields. They distinguish
`unresolved_binding`, `deferred_binding_source`, `orphaned_override`, `terminal_origin_mismatch`,
`storage_degraded` and others. **Most are not persisted.** The accepted reconcile/verify ADR records
36 of 38 as not persisted, so they must be captured at calculation time.

The work review (`src/cadrumo/application/modelo/work_review.py:107`) projects each casilla's
`concrete_bindings` as `(binding_id, source, resolved)`, plus `realised_kind`, `absent_by_design` and
`origin_anomaly`. `resolved` means "present in the replay map", not "came from its source".
`OPERATOR_OVERRIDE` is raised only when a bound casilla's observation disagrees with its persisted
binding value (`_work_review_assembly.py:259-276`). A binding-level override is invisible to it,
because the persisted binding value **is** the override. The workspace never carries this review:
the facet is `UNMEASURED` (`workspace.py:189`, `:1592`).

##### 1.4 What the product lets a user do per source today

TUI (sections 1-10 of the exploration pass):

| Source family | TUI surface | Link to/from the modelo workspace |
|---|---|---|
| Ledger (bank CSV/OFX/XLSX/PDF-N26), invoice books, manual invoice, evidence extraction, classification, reconciliation | `ledger/import_flow.py:89`, `ledger/classification.py:75`, `ledger/evidence.py:73`, `ledger/reconciliation.py:37` | None. The reconciliation "affected declarations" rows (`reconciliation.py:153-165`) are not selectable. |
| Withholding (retenciones_aggregation for 111/115/180/190) | `withholding/screen.py:64` (append / replace / clear captures) | None. The screen uses hard-coded English labels (`screen.py:100-117`). There is no capital-income family for 123/193. |
| Profile (profile bindings) | `profile/overview.py:472`, with `FieldEditScreen` at `:173` | F4 opens it from anywhere; there is no way back or deep link to a field. The source buttons are hidden because the launcher passes no `launch_source` (`launcher.py:519-535`). |
| AEAT sync (filed history, census) | `aeat_sync/screens.py` | Read-only in practice: `operation_handoff` is never supplied (`launcher.py:1212-1221`). |
| Previous filings / external import, local observations, spreadsheet, IVA wallet, borrador, inventory, bienes de inversión, prorrata register | none | none |
| Modelo workspace edit | `overview.py:181-197`: one bare `Input` per manual casilla and per manual_input binding | Submits only `SET_TYPED_VALUE` and `SET_OVERRIDE_VALUE` (`modelo/lifecycle.py:129-169`). `CLEAR_DECLARED_VALUE` and `REMOVE_OVERRIDE` are never sent. |
| Modelo workspace provenance | `modelo/view/provenance.py`: a flat table of (subject, source_ref), with the resolver in a collapsed group | Read-only, with no drill-through. |

CLI:

- `aeat app modelo work calculate` accepts:
  - `--casilla` and `--binding` (for non-locked sources)
  - `--relation` and `--row`
  - `--borrador`
  - shortcut flags
- Discovery commands:
  - `modelo bindings list --missing`
  - `modelo bindings resolve`: echoes the binding and its readiness only, with no value
  - `modelo requires`: the `data_inventory` checklist
  - `modelo work observations`
- Import commands: `modelo filing-record import` and `observe-local --clear` (the only clear in the
  CLI), `modelo iva-wallet seed|correct|override`, `live borrador 100 import`,
  `live filed pull|pull-all`, `ledger import`, `ledger invoice import`, and
  `config profile censo import --file`.
- `modelo spreadsheet push|export|pull`: a round trip that saves nothing.
- Each CLI calculate is memoryless: leaving a flag out on the next run clears it.
  (`src/cadrumo/entrypoints/cli/_modelo_work_calculate_cli.py:343`,
  `_modelo_cli_support.py:192/259/282/401`, `calculate_input.py:489/545`.)

**What the modelo workspace is missing:** a single place that shows each source, what it filled,
whether it resolved, why not, and what to do next. Beyond that, it cannot:

- deep-link to the owning source surface;
- apply the carry override that the product's own advisory recommends (`relation_prefill.py:872`:
  "Supply the value … through a binding override on calculate");
- clear a value or remove an override;
- show the calculation diagnostics.

##### 1.5 Reusable building blocks already in the tree

- `data_inventory_checklist` (`src/cadrumo/application/modelo/data_inventory.py:196`) already sorts
  a revision's casillas into required/optional manual, detail-row, ledger, profile, previous-filing,
  relation-prefill, live-observation and unbucketed groups, with unresolved profile keys. It is
  casilla-keyed, so it misses formula-only and fichero-only bindings.
- `SourceActionCard` / `SourceActionDescriptor` (`components/widgets.py:398-455`) is a titled "Get
  data" card with an action button.
- `RequirementBadge` and `RequirementStatus` (`widgets.py:328-377`) give a glyph plus a label, never
  colour alone.
- `DisclosureGroup`, `NoticeBand` and `ContentDataTable` (`widgets.py`).
- The profile `FieldEditScreen` (`profile/overview.py:173`) has what/why/where help
  (`field_help_text`, `:155`).

---

#### 2. Proposed design

##### 2.1 Principles

1. **Every value names its origin.** No casilla value is ever shown without a source chip, even
   when it is "you" or "nothing found".
2. **Six states that never collapse into each other.** Imported, nothing found (proven zero or
   absent by design), missing, not importable yet (deferred), your value, and overridden. Each has
   its own glyph and word (§2.3). A zero is always shown with its reason.
3. **Fix numbers at their source.** Ledger-locked values are corrected in the books, and the
   workbench takes the user straight there. Only carry sources can be overridden, and an override
   needs a reason and is disclosed forever after.
4. **The schema drives the panel.** Every row, grouping, action and sentence derives from registry
   data plus one small typed table per source kind (§2.8). A new modelo gets its Sources panel
   without writing any UI code.
5. **Recalculating never silently discards the user's work.** "Recalculate with the current
   sources" keeps the user's values and overrides. "Discard my changes" is a separate, confirmed
   action.

##### 2.2 Where it sits

The workbench gets a **Sources** tab (Spanish: "Procedencia") next to Casillas, Results, Checks and
File, and every casilla row carries a compact origin chip (shared with lens B). Pressing `Enter`
on a chip, or `g`, opens the same **"Where does this come from?"** drill-down that the Sources tab
uses. The tab is the "import and review" hub, and the chip is how the user gets there from a number.

##### 2.3 State vocabulary (glyph + word, catalogue-keyed)

| Glyph | Word (en / es) | Meaning | Derived from |
|---|---|---|---|
| `●` | Imported / Importado | A source resolved a value | Binding present in the replay map, with a provenance row of that source kind and no operator marker |
| `○` | Nothing found / Sin datos | The source was consulted and legitimately holds nothing, so 0 is proven | `absent_by_design`, or a resolved zero backed by a provenance row or an empty-register attestation |
| `✖` | Missing / Falta | The source was expected but produced nothing, and the value is unknown | `unresolved_binding` or an unresolved relation diagnostic, or a required casilla still EMPTY |
| `◐` | Not importable yet / Aún no importable | The source kind is `deferred`, so the user must enter the value | Provider disposition `deferred`, or the `deferred_binding_source` diagnostic |
| `✎` | Your value / Valor suyo | Typed by the user, or taken from a file the user imported | Operator-input axis (new, §2.7) |
| `⚑` | Overridden / Sustituido | The user's value replaces an imported value; both are shown | Operator override marker plus the source value captured at override time |
| `!` | Check this / Revisar | A calculation advisory is attached | Captured `CalculationSourceDiagnostic` whose `binding_id` or `relation_id` joins the row |
| `⟳` | Out of date / Desactualizado | The source has changed since the last calculation | Provenance fingerprint drift, or a ledger snapshot drift |
| `—` | Not applicable / No aplica | Applicability excludes this row for this filer or period | `binding.applicability` and the profile gate |

`!` and `⟳` are modifiers that combine with a primary state, as in `⚑⟳` or `●!`. `✎` and `⚑` are
different on purpose: typing a value into an empty manual box is not overriding evidence.

##### 2.4 Sources tab at 120x36 (Modelo 303, 1T 2025, synthetic values)

```text
┌ Cadrumo · Modelo 303 IVA · 1T 2025 · borrador ──────────────────────────────────────────── F1 Ayuda · F4 Perfil ─────┐
│  Casillas   [ Procedencia ]   Resultados   Comprobaciones   Presentar         ● 46  ○ 4  ✖ 1  ◐ 0  ⚑ 0  ! 1          │
├──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ Mostrar: (•) Todo  ( ) Requiere atención  ( ) Mis valores        Buscar: [               ]   Calculado 12-04 10:32   │
│                                                                                                                      │
│ ▾ Sus apuntes · libro de IVA y facturas                  47 filas · ● 45  ○ 2       [Importar] [Abrir libro]         │
│   Estado            Qué rellena                                 Casilla        Valor   De dónde sale                 │
│   ● Importado       Base imponible régimen general 21 %         07         12 400,00   14 apuntes de IVA             │
│   ● Importado       Cuota régimen general 21 %                  09          2 604,00   14 apuntes de IVA             │
│   ○ Sin datos       Base imponible 10 %                         04              0,00   ningún apunte al 10 %         │
│   ● Importado       Base IVA soportado operaciones interiores   28          3 150,00   9 facturas recibidas          │
│   … 43 más                                                                             [Ver todas]                   │
│ ▾ Declaraciones anteriores                                   1 fila · ✖ 1                                            │
│ ▸ ✖ Falta         Cuotas a compensar de periodos anteriores   110                  —   303 de 4T 2024: no está       │
│ ▸ Registros propios · bienes de inversión, prorrata          2 filas · ○ 2                                           │
│ ▸ Su perfil                                                  2 filas · ● 1  ! 1      [Editar perfil]                 │
├─ ¿De dónde sale la casilla 110? ─────────────────────────────────────────────────────────────────────────────────────┤
│ Cuotas a compensar de periodos anteriores                                                   ✖ Falta · obligatoria    │
│                                                                                                                      │
│ Esta casilla arrastra el saldo a compensar que quedó al final de su Modelo 303 de 4T 2024.                           │
│ Cadrumo ha buscado en sus declaraciones presentadas y en su monedero de IVA y no lo ha encontrado.                   │
│ Si tenía saldo a compensar y lo deja vacío, pagará más de lo que debe.                                               │
│ Regla: [referencias legales de la vinculación, desde el registro]                                                    │
│                                                                                                                      │
│ Qué puede hacer                                                                                                      │
│  [i] Importar la declaración de 4T 2024 (justificante o copia AEAT)   [a] Traer el historial presentado de AEAT      │
│  [e] Indicar el importe de su copia (con motivo y justificante)       [o] Abrir el 303 de 4T 2024                    │
│                                                                                                                      │
│                                                                                                                      │
│                                                                                                                      │
│                                                                                                                      │
│                                                                                                                      │
│                                                                                                                      │
├──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ ↑↓ mover · Intro detalle · e indicar/sustituir · x quitar sustitución · g ir al origen · c recalcular · ? leyenda    │
└──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

Notes:

- Family order is fixed by the family table (§2.8). A family that needs attention opens
  automatically, and the others stay collapsed with glyph counts in the title. This is the
  profile-manager fold language.
- "De dónde sale" is the plain sentence from `docs.casilla.binding_source.*`, filled with counts
  from the source projection (§2.9). The raw `source_ref`, resolver and binding id stay in the
  collapsed technical-details group that already exists (`technical_details.py`).
- "Qué rellena" is the label of the target casilla. For a formula-only binding it becomes "Used to
  compute casilla N (label)". For a fichero-only binding it uses the new binding label key (§2.8).
  A raw id is never the primary text.
- The header counter strip is the pre-filing honesty summary: missing, deferred and advisory counts
  are always visible.

##### 2.5 Sources tab at 80x24 (same state)

```text
┌ 303 IVA · 1T 2025 ─────────────────────────────────────── ● 46 ○ 4 ✖ 1 ! 1 ──┐
│ Casillas [Procedencia] Resultados Comprobar Presentar                        │
├──────────────────────────────────────────────────────────────────────────────┤
│ Mostrar: Requiere atención ▾                                                 │
│ ▾ Declaraciones anteriores                                     ✖ 1           │
│   ✖ 110 Cuotas a compensar periodos ant.                  —  303 4T 2024     │
│ ▾ Su perfil                                                    ! 1           │
│   ! 65  Porcentaje atribuible Estado                  100,00  perfil         │
│ ▸ Sus apuntes (libro IVA)                              ● 45  ○ 2             │
│ ▸ Registros propios                                    ○ 2                   │
│                                                                              │
│                                                                              │
│                                                                              │
│                                                                              │
│                                                                              │
│                                                                              │
│                                                                              │
│                                                                              │
│                                                                              │
│                                                                              │
│                                                                              │
├──────────────────────────────────────────────────────────────────────────────┤
│ Intro detalle · e indicar · g origen · c recalcular · ? leyenda · q volver   │
└──────────────────────────────────────────────────────────────────────────────┘
```

At 80 columns:

- "Where it comes from" shrinks to a short source token.
- The detail pane becomes a full-screen modal, opened with `Enter`.
- The default filter is "needs attention", so the first screen is the to-do list and not 47 ledger
  rows.

##### 2.6 Drill-down: a ledger-locked casilla at 120x36

```text
┌ ¿De dónde sale la casilla 07? ───────────────────────────────────────────────────────────────────────────────────────┐
│ Base imponible · régimen general 21 %                                         12 400,00 €   ● Importado              │
│                                                                                                                      │
│ Sale de sus apuntes de IVA: la suma de la base de 14 apuntes de 1T 2025 clasificados como «general 21 %».            │
│ Este importe lo calcula Cadrumo a partir de sus libros; no se escribe a mano. Si no es correcto, corrija o           │
│ reclasifique los apuntes y vuelva a calcular: la declaración siempre coincide con sus libros.                        │
│                                                                                                                      │
│   Fecha        Contraparte              Concepto                         Base       Cuota   Clasificación            │
│   03-01-2025   Cliente A (sintético)    Factura 2025-001               1 000,00     210,00  general 21 %             │
│   17-01-2025   Cliente B (sintético)    Factura 2025-002                 850,00     178,50  general 21 %             │
│   …                                                                                                                  │
│   12 apuntes más                                                         [Ver todos en el libro]                     │
│                                                                                                                      │
│ También a revisar: 2 apuntes de 1T sin clasificar podrían corresponder a esta casilla.    [Clasificar]               │
│ Regla: [referencias legales de la vinculación]      Fuente oficial: [source_refs de la vinculación]                  │
│ Último cálculo 12-04-2025 10:32 · sus libros no han cambiado desde entonces.                                         │
│                                                                                                                      │
│ [g] Abrir estos apuntes en el libro     [i] Importar extracto o facturas     [?] Por qué no puedo editarlo           │
│                                                                                                                      │
│ ▸ Detalles técnicos (vinculación, resolutor, referencias de origen)                                                  │
│                                                                                                                      │
│                                                                                                                      │
│                                                                                                                      │
│                                                                                                                      │
│                                                                                                                      │
│                                                                                                                      │
│                                                                                                                      │
│                                                                                                                      │
│                                                                                                                      │
│                                                                                                                      │
│                                                                                                                      │
│                                                                                                                      │
│                                                                                                                      │
├──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ g ir al libro · i importar · Esc volver                                                                              │
└──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

The per-entry list needs a binding-keyed contributor projection that does not exist yet (Bug B14,
§2.9). Until it exists, the drill-down honestly says "14 entries in your IVA ledger for 1T". It gets
that count from provenance rows of `resolved_binding_source = ledger_iva_aggregation`, and must not
invent a per-casilla split.

##### 2.7 Override lifecycle

The "Indicar / sustituir" dialog for a carry is modelled on the existing `IvaCompensationOverride`
fields: amount, reason and evidence locator.

```text
┌ Indicar el importe · casilla 110 ─────────────────────────────────────────────┐
│ Cuotas a compensar de periodos anteriores                                     │
│ Origen previsto: su Modelo 303 de 4T 2024 (no encontrado)                     │
│                                                                               │
│ Importe (€)          [ 1 250,00           ]   formato: 1 234,56               │
│ Motivo               [ Copia en papel del 303 de 4T 2024                  ]   │
│ Justificante         [ Carpeta Hacienda/2024/303-4T.pdf                   ]   │
│                                                                               │
│ Este valor sustituye al que Cadrumo importaría. Quedará marcado como          │
│ «Sustituido» en la declaración y en el informe de revisión.                   │
│                                                                               │
│                              [Cancelar]  [Guardar y recalcular]               │
└───────────────────────────────────────────────────────────────────────────────┘
```

The state machine for one source row:

```text
          import resolves                      user overrides (carry only, reason required)
 (none) ───────────────▶ ● Imported ──────────────────────────────────────────▶ ⚑ Overridden
    │                      ▲   │ source changes                                   │   │ source changes
    │ nothing resolves     │   ▼                                                  │   ▼
    ├──────────▶ ✖ Missing  │  ●⟳ Out of date ── recalculate ──▶ ● Imported       │  ⚑⟳ "source now says X"
    │                │     │                                                      │
    │                └─ user enters value (carry) ─────────────────────────────▶ ⚑ Overridden (source = none)
    │                                                                              │
    └──▶ ○ Nothing found                         x remove override ◀───────────────┘ → back to ● / ✖ / ○
```

Rules:

- **LOCK sources** (the ledger/invoice family and, at run time, retenciones_aggregation, withholding,
  foreign_asset and atribucion_member):
  - The row offers no edit action. `e` explains why and offers `g`.
  - The wording mirrors `_reject_caller_overrides_of_source_bindings`: "the declaration would no
    longer reflect the records it claims to add up".
- **CARRY sources** (previous_filing, relation_prefill, iva_compensation_annual_partition,
  prorrata_regularizacion):
  - The user may override.
  - Amount, reason and evidence locator are all mandatory.
  - The source value and fingerprint at override time are captured and shown alongside the user's
    value for as long as the override exists. The 303 casilla 110 carry routes through the IVA-wallet
    override service rather than a generic binding override.
- **Profile:**
  - Editing opens the profile `FieldEditScreen` for the underlying profile key, inline.
  - It is **not** a per-declaration override: the fact is corrected once, at its home.
  - `data_inventory` already maps a binding to its profile keys (`data_inventory.py:169`).
- **`manual_input` bindings and manual casillas:** typed entry with `✎`, plus explicit **Clear**,
  which produces a new, stated state: "Cleared (you removed the value)". That is distinct from never
  being set.
- **Unclassified sources** (17 kinds): shown read-only with "Can this be changed by hand? Not yet
  decided", until the schema table (§2.8) classifies them. The UI never guesses.
- **Every calculation carries all current overrides and user values forward.** Removal is always an
  explicit `x`. It sends `REMOVE_OVERRIDE` or `CLEAR_DECLARED_VALUE`, and is never done by leaving a
  field empty.
- **Before filing**, the Presentar tab lists every `⚑` row with its source value, the user's value,
  the difference, and the reason (disclosure of override divergence).

**Persistence this requires** (the application layer owns it; the TUI must not):

- An operator-input axis on the revision (or an encrypted per-work-unit override store). For each
  entry it records the binding or casilla, the value, the reason, the evidence locator, `recorded_at`,
  the source value and fingerprint at override time, and whether the entry is an override or a plain
  entry.
- The edit executor re-supplies that axis on every calculation (the D4 "absence means unchanged"
  rule).
- The merge step emits an `override_divergence` diagnostic whenever the caller tier shadows a
  resolved lower tier.

##### 2.8 Schema-level contract: how every modelo defines its import interface

Nothing in this panel is authored per modelo. The inputs it needs are:

1. **Per source kind: one total, typed table** (a new application or core mapping validated against
   `BindingSourceKind`). It adds three columns to the axes that already exist:
   - `family`, one of:
     - `records` (ledger and invoices)
     - `registers` (withholding, inventory, bienes, prorrata, foreign assets, attribution, donativos)
     - `profile`
     - `earlier_filings` (previous filing, relation prefill, the IVA annual partition, the 303
       summary, the IVA wallet)
     - `aeat` (borrador)
     - `your_entries` (manual_input)
     - `fixed_by_aeat` (design_constant)
   - `override_policy`, one of `fix_at_source`, `override_with_reason`, `edit_at_home` (profile),
     `enter` (manual) and `fixed`. It must be **total**, which turns the 17 currently unclassified
     kinds into an explicit decision. It must also be conformance-bound to
     `CALLER_OVERRIDE_PRECEDENCE_LADDER`, in the way `test_precedence_ladder_conformance` already binds
     the lock and carry sets.
   - `destination`: a typed navigation target, such as `workbench.ledger/import`,
     `workbench.withholding`, `workbench.profile/field:<key>`, `modelo.filing_record.import`,
     `aeat_sync/filed`, `borrador.import` or `none_yet`. It resolves to a real route or to an explicit
     "not available in the app yet" state.

   A prototype (`proto_panel.py`) builds this table for all 33 kinds and asserts that it is total. It
   then derives every figure in the census table in §1.2 with no per-modelo code.
2. **Per binding: an optional catalogue label/help key**, analogous to the casilla `localization_keys`.
   It is required for bindings no casilla names (fichero-only and formula-only). The fallbacks, in
   order, are the target casilla label, then the export field's design label, then a humanised id
   shown with a "technical name" marker.
3. **Per revision:** the existing `binding_consumers` (which casillas, formulas and export fields a
   binding feeds), `applicability`, `legal_refs`, `source_refs` and `terminal_origins`.

##### 2.9 Application projection the panel consumes

This is a new read model. It is renderer-neutral, holds no financial values in logs, and lives in
the application layer. Its name, for example `ModeloSourceReviewV1`, belongs to lens A.

- **One row per binding.** Each row carries the binding id and label key, the family, the policy,
  the provider disposition, the consumers (casilla ids, formula ids and export fields), the state
  from §2.3, the current value, and the source value at override time when there is one.
- **Contributor summary** per row: count, period window and destination handle. The handle is a
  typed parse of `source_ref`, not string splitting in the TUI.
- **Diagnostics** captured at calculation time and joined by binding or relation id, with message
  and remedy.
- **Staleness:** whether the recorded provenance fingerprints still match current source state.
- **Grouping** by family, with counts per state.

It builds on `data_inventory_checklist` (extended to cover bindings with no casilla consumer), the
work review, `source_provenance` and `source_issues`. It needs two new captures:

- The diagnostics of the last calculation.
- A binding-keyed contributor link. Either add `binding_id` to `CalculationSourceProvenance` and
  `CalculationSourceRef`, or run a read-only "explain" re-projection of the resolver. **Do not infer
  it from `source_casilla_ids`** (see B5).

##### 2.10 Plain-language explanation templates

These are catalogue keys, with one template per family and state. Examples in en:

- **Records, imported:** "Added up from {n} entries in your {ledger} for {period}. Cadrumo does not
  type this number; it follows your books. To change it, correct the entries."
- **Records, nothing found:** "None of your entries for {period} belong in this box, so it is 0."
- **Earlier filing, missing:** "This carries {what} from your Modelo {m} for {period}. Cadrumo could
  not find that filing. If you had an amount to carry, leaving this empty means you pay more than
  you owe."
- **Earlier filing, overridden:** "You entered {yours} instead of the {source} Cadrumo found in your
  Modelo {m} for {period}, because: {reason}."
- **Register, not importable yet:** "Cadrumo cannot read {register} yet. Enter the amount from your
  own records."
- **Profile, missing:** "This comes from your taxpayer profile ({field}), which is empty. Fill it
  once and every declaration that needs it will use it."
- **Your value:** "You typed this value on {date}." **Cleared:** "You removed the value on {date}; it
  is now empty on purpose."

##### 2.11 Per-source actions (what each button does)

| Family | Primary actions | Destination today |
|---|---|---|
| records | Import statement or invoices (pre-filtered to the period); Classify pending entries (n); Show entries used | `workbench.ledger` import, classification and entries (exist); a deep link with a period filter is new |
| registers | Record withholding (scoped to the modelo and period); Inventory, bienes, prorrata | Withholding exists (it needs localising). Inventory, bienes and prorrata show "not available in the app yet" plus the value-entry path when the policy allows it |
| profile | Edit this fact inline | `FieldEditScreen` (exists) |
| earlier_filings | Import the filed declaration; Fetch filed history from AEAT; Open that filing's workspace; Enter the amount from your copy | External import and IVA-wallet override exist in the application layer, with no TUI. AEAT sync filed history exists but is unwired. Opening another work unit exists through Declarations |
| aeat (M100) | Import borrador; Choose snapshot | Application and CLI only |
| your_entries | Enter, Clear | The edit contract (needs clear wired in the TUI) |
| all | Recalculate keeping my values; What changed since the last calculation | New; see B1 and B3 |

A spreadsheet round trip belongs in the same hub as an import: "Import values from a spreadsheet".
Every imported cell lands as `✎` with origin "file {name}, {date}" after a diff review. The CLI
`spreadsheet pull` saves nothing today, and `observe-local --file` writes past-period observations,
which is a different channel. Before a TUI "import spreadsheet" is offered, an application decision
must say which channel it feeds.

---

#### 3. Suggestions ranked by user value against effort

| # | Suggestion | User value | Effort |
|---|---|---|---|
| 1 | Carry user values and overrides forward on every edit and on Calculate. This needs an explicit operator-input axis, and must not replay the merged `input_values_by_casilla_id` (§1.3) | Critical: today a second edit or pressing Calculate silently discards work | Medium (application) |
| 2 | Capture calculation diagnostics in the TUI calculate and edit operations and show them on source rows plus the header strip | High (no-silent-under-declaration) | Low-medium |
| 3 | Show an origin chip on every casilla row, using the plain-language `docs.casilla.binding_source.*` keys that already exist | High | Low |
| 4 | Build the Sources tab from `data_inventory_checklist` extended to bindings with no casilla consumer, with family grouping and state glyphs | High | Medium |
| 5 | Deep links from a source row to Ledger import and classification, Withholding and a Profile field (inline `FieldEditScreen`) | High | Low-medium (routes exist) |
| 6 | A total source-kind table (family, policy, destination) with a conformance test against the ladder | High; unlocks schema-driven UI | Low |
| 7 | Carry override with reason and evidence, plus remove override (wire `REMOVE_OVERRIDE` and `CLEAR_DECLARED_VALUE`), plus a divergence diagnostic | High for 303 casilla 110, 130 casilla 05 and the M390 and M100 carries | Medium-high |
| 8 | Fix the provenance subject attribution for carries (B5) and show the source filing and period as "from Modelo M, period P, casilla C" | Medium-high (correctness) | Low |
| 9 | A binding-keyed contributor projection ("which 14 entries") | High for trust | Medium |
| 10 | Binding label and help catalogue keys (fichero-only fields such as M390's 173) | Medium; large modelos only | Medium (content) |
| 11 | Earlier-filing import in the TUI (justificante, AEAT filed-history pull) | Medium-high | Medium (application exists) |
| 12 | A stale-source indicator (`⟳`) from fingerprint drift | Medium | Medium |
| 13 | Borrador (M100), inventory, bienes and prorrata surfaces | Medium, M100 and annual modelos | High |

---

#### 4. Bugs noted (not fixed)

| ID | Severity | Finding | Evidence |
|---|---|---|---|
| B1 | Critical | **Edits are memoryless.** The edit executor builds casilla inputs and binding values only from the submitted intents, while calculation is memoryless, so a second edit drops every earlier manual value and binding override. Detail rows are the one thing it carries. It also drops `borrador_snapshot_id`, relation values, IVA compensation decision, M210 codes and filing-instance evidence. | `src/cadrumo/application/modelo/_edit_execution.py:102-133`, `:338-350`; `calculation_actions.py:1431-1456` |
| B2 | Critical | **The TUI "Calculate" button** sends only the work unit id (`modelo/lifecycle.py:86-107`), and the executor calls calculate with no inputs (`operation_definitions.py:385-433`). Pressing it re-derives from the ledger alone and discards all manual values, overrides and detail rows. It also returns only the revision id, which drops every source diagnostic. | as cited |
| B3 | High | **Edit apply cannot succeed on Modelo 303.** `_execute_modelo_edit` passes no `filing_instance_evidence`, and `validate_m303_filing_instance_evidence_for_revision` raises `missing` for 303 when it is `None`. Inferred from code; not executed. | `_edit_execution.py:338-350`; `src/cadrumo/application/modelo/m303_filing_evidence.py:83-89` |
| B4 | High | **`REMOVE_OVERRIDE` is refused** as not yet wired. The TUI never sends `CLEAR_DECLARED_VALUE` or `REMOVE_OVERRIDE`, and an empty input means "unchanged", so a user cannot clear a value or withdraw an override. | `_edit_execution.py:249-253`; `modelo/lifecycle.py:129-169`; `overview.py:355-370` |
| B5 | High | **The workspace provenance page misattributes carries.** For previous_filing and relation_prefill, `source_casilla_ids` names casillas **of the source filing**, but `graded_snapshot_provenance_records` renders them as subject casillas of the current revision. Measured examples: the 303 carry names `iva.compensacion-disponible-fin-periodo` while it fills 110; 130's `pagos-fraccionados-anteriores` names `07` and `16` (which exist in the current 130 with other meanings) while it fills 05; 100's `base-liquidable-negativa-general-anterior` names `1391` while it fills 1388. | `src/cadrumo/domain/calculations/registry/bindings.py:561-562`; `application/calculations/binding_prefill.py:783`; `relation_prefill.py:1302`; `workspace.py:1962-1985`; `srccas.py` output |
| B6 | High | **Caller values silently shadow resolved sources.** `absorb_by_precedence` overlays tiers with no divergence signal. The shadowed tier's provenance rows are still persisted, so the revision claims a carry came from the related filing when the operator typed it, and the review classifier cannot detect a binding-level override. This conflicts with the registry-bindings rule that user values never silently override a higher-authority binding. | `application/aggregation/source_resolution_operations.py:151-170`; `calculation_resolution.py:174-180`, `:335-342`; `_work_review_assembly.py:259-276` |
| B7 | High | **The admission surface is narrower than the accepted edit-contract amendment.** Only `MANUAL_INPUT` bindings are writable, while the amendment admits every non-lock, non-date binding. The carry override the product itself recommends in the relation-prefill advisory remedy is unreachable from the TUI. | `edit_admission.py:161-178`; `relation_prefill.py:872`, `:893`; ADR `2026-08-24-modelo-edit-contract-adr` amendment "REMOVE_OVERRIDE is binding-addressed" |
| B8 | Medium | **The override policy is not declared for 17 of 33 source kinds.** The effective lock for retenciones, withholding, foreign asset and attribution is decided only at run time by resolver ownership, so no UI can know statically whether 111 and 115 values can be overridden. | `source_mesh.py:390-423`; `calculation_actions.py:1349-1354` |
| B9 | Medium | **`binding_overrides` is misnamed:** it holds every resolved binding value. `ModeloWorkBindingOrigin.resolved` means "materialised", not "came from its source". No persisted marker says which values the operator supplied. | `calculation_resolution.py:335-342`; `_work_review_assembly.py:352-362` |
| B10 | Medium | **`data_inventory` is casilla-keyed**, so `modelo requires` omits formula-only and fichero-only bindings. Measured: 130 has 2, 100 has 16, and 390 has 173 fichero-only. | `data_inventory.py:307-338` |
| B11 | Medium | **Ledger and invoice provenance rows carry no binding or casilla link**, and `CalculationSourceProvenance` has no `binding_id`. "Which entries make up casilla 07" cannot be answered from the persisted revision. | `source_mesh.py:673-704`; `aggregation/modelo_bindings.py:505-514` |
| B12 | Low-medium | **Orphan bindings.** 130 declares 3 ledger bindings with no consumer: taxable-base, rendimiento-neto and retenciones cumulative. 347 declares 2 declarante-summary bindings (count of counterparties, total annual amount) with no consumer, while all 43 of its casillas are manual, so the user types totals the ledger could compute. This may be intentional; it needs adjudication. | `census2.py` output |
| B13 | Low-medium | **The withholding capture screen hard-codes English labels** and is a plain `Screen`, which breaks the locale contract. | the former source file |
| B14 | Low | **AEAT sync operations and profile "source" buttons are never mounted.** The launcher passes no handoff or `launch_source`. | `launcher.py:1212-1221`, `:519-535` |
| B15 | Low | **The edit baseline is admitted once**, when the workspace is composed, and expires after 5 minutes, so a longer session is refused as stale at submit. This was already recorded by the workbench reference. | `launcher.py:1035`; `edit_admission.py:57` |

---

#### 5. Risks and open questions

- **Operator-input axis versus replay.** Carrying forward `input_values_by_casilla_id` or
  `binding_overrides` would freeze source values as user values, because both maps are merged
  (§1.3). The fix needs a new explicit axis, and a decision on whether it joins the
  content-addressed revision identity. It should, because a revision computed with a user override
  is a different filing.
- **Which overrides are legal.** Deciding `override_with_reason` versus `fix_at_source` for profile,
  retenciones, withholding, bienes, borrador and the IVA wallet is a tax-policy decision, not a UI
  one. Until it is decided, the UI must show "not yet decided" rather than guess.
- **The 303 casilla 110 carry has its own authority** (the IVA-wallet reconciliation). A generic
  binding override must not bypass it.
- **Spreadsheet import semantics.** Current-period user values, past-period observations and a
  round-trip check are three different things. An application decision should come before any TUI
  affordance.
- **Contributor projection cost and privacy.** Listing contributing entries shows NIFs and names on
  screen, which is fine in the TUI. They must never enter operation journals, logs or route keys,
  following the edit contract D7.
- **Stale-source detection** needs fingerprints for every resolver. Some emit `fingerprint=None`, so
  those rows would show `⟳ unknown`, not `●`.
- **Measurement scope.** The census counts authored-and-hydrated structure from an in-memory
  structural compile, not a published generation, and uses each modelo's latest revision. Earlier
  revisions, for example 303 for 2025 filings, may differ. B3 is inferred from code and was not
  executed.

#### 6. Overlap notes

- **Lens A (form model):** the §2.9 projection should be a peer of the casilla form model, keyed by
  binding id and joined to casillas through `binding_consumers`. A needs these fields per casilla:
  origin state (§2.3), origin family and sentence key, override policy, and whether an operator value
  is present. The binding label key (§2.8.2) belongs in the same schema-surface catalogue as the
  casilla labels.
- **Lens B (row hints):** the chip is `glyph + short source token`, for example "● libro IVA (14)",
  "⚑ su valor", "✖ 303 4T 2024" or "○ sin datos". It must render without colour and never show a
  bare 0 without a reason word.
- **Lens C (editing):** override and clear are separate intents from set. Their dialogs need reason
  and evidence fields for carries, and B1, B3 and B4 are prerequisites for any editing to be
  trustworthy. An empty input must never mean "remove".
- **Lens E (flow):** Sources is the hub that links out to Ledger, Withholding, Profile and AEAT sync
  and returns to the same row. Those areas need a "return to modelo X" affordance and period-scoped
  entry. The Declarations to workspace entry point stays; Home "action rows" could list "303 1T: 1
  source missing".

## Sources

- `src/cadrumo/application/aggregation/source_mesh.py:390`
- `src/cadrumo/application/modelo/_edit_execution.py:102-133`
- `src/cadrumo/application/modelo/calculation_resolution.py:139-180`
- `src/cadrumo/application/modelo/data_inventory.py:196`
- `src/cadrumo/application/modelo/m303_filing_evidence.py:83-89`
- `src/cadrumo/application/modelo/work_review.py:107`
- `src/cadrumo/core/aggregation.py:226`
- `src/cadrumo/domain/calculations/registry/authority.py:969`
- `src/cadrumo/domain/calculations/registry/bindings.py:561-562`
- `src/cadrumo/domain/calculations/registry/schema.py:263`
- `src/cadrumo/domain/modelos/calculation_revision.py:803-905`
- `src/cadrumo/entrypoints/cli/_modelo_iva_wallet_cli.py:209`
- `src/cadrumo/entrypoints/cli/_modelo_work_calculate_cli.py:343`

- `src/cadrumo/locales/*/docs.yml`
