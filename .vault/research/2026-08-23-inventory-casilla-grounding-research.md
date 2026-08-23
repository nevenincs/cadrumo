---
tags:
  - '#research'
  - '#inventory-casilla-grounding'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:6f802210dda5700a4c78288fc5125b36879f7b4c532eda775859ca6650a03806'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
  - "[[2026-08-22-modelo-work-binding-architecture-inventory-gap-verification-reference]]"
  - '[[2026-07-05-modelo-720-row-carrier-adr]]'
---

# `inventory-casilla-grounding` research: `Modelo 100 stock valuation mapping`

Official 2025 evidence supports three inventory outputs for each direct-estimation economic activity: purchases in 0181, positive closing-minus-opening variation in 0177, and the magnitude of negative variation in 0182. The source-domain gaps, S43 grounded operation templates, S170-S175 row-source identity transport/persistence/replay/redaction, and S176 runtime cohort expansion are implemented. Runtime inspection exposes two remaining seams: row binding values survive as identified source rows but never become row-indexed casillas, and the supported XML filing surface requires a complete repeated activity envelope that inventory does not own. AEAT's XSD proves XML row capability; no outbound PDF format or official repeated-PDF coordinate contract exists in the application. The mapping ADR must therefore keep direct row-casilla materialisation separate from the activity-envelope join and format-specific rendering.

## Findings

### The official 2025 form separates purchases and both directions of stock variation

The Modelo 100 direct-estimation activity page lists inventory increase among income, then inventory purchases and inventory decrease among deductible expenses. Their boxes are 0177, 0181, and 0182. Because the page is activity-scoped, the projection grain is one `(taxpayer, filing year, activity)`, not one taxpayer-wide scalar. Orden HAC/277/2026 approves this form for tax year 2025. Evidence: https://www.boe.es/eli/es/o/2026/03/25/hac277/dof/spa/pdf, page 27; `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025/casillas/c0177.toml:1`, `c0181.toml:1`, and `c0182.toml:1` in that directory.

The alternatives are one signed output, three unsigned presentation facts, or a consumption scalar. The official presentation rejects the signed output and consumption scalar as direct destinations: it requires purchases independently and routes variation according to sign. The evidence favors `0177 = max(closing - opening, 0)` and `0182 = max(opening - closing, 0)`, with a mutual-exclusion invariant.

### Purchases are acquisition cost, not always the current IVA-exclusive movement value

The AEAT manual defines inventory purchases as current-goods acquisitions from third parties for earning income. Acquisition price includes directly attributable costs and indirect taxes that are not directly recoverable; deductible input IVA is excluded. Evidence: https://sede.agenciatributaria.gob.es/static_files/Sede/Biblioteca/Manual/Practicos/IRPF/IRPF-2025/ManualRenta2025Parte1_es_es.pdf, pages 424-426.

At the original decision baseline, the movement value was IVA-exclusive and the purchase subtotal omitted non-deductible IVA and attributable costs. Evidence: commit `159465372d`, `src/cadrumo/domain/contribuyente/inventory/__init__.py:89-148`, `:406-433`, and `:436-476`. Commits `3c22586e1b` through `bd182527db` subsequently implemented `InventoryAcquisitionCost`, `MovementRecord.acquisition_cost`, complete acquisition totals, and the casilla 0181 projection; current locators are `src/cadrumo/domain/contribuyente/inventory/__init__.py:203-245`, `:736-789`, `:1025-1097`, and `:1325-1356`. The runtime-row question does not reopen that settled source fact.

### Stock variation is closing value minus opening value, split by sign

The AEAT manual defines variation as the difference between opening and closing stocks. Closing above opening is income; opening above closing produces an expense of the difference. It also requires the next period's opening value to equal the prior closing value and accepts acquisition price or production cost, with weighted-average cost and FIFO for homogeneous groups. Evidence: https://sede.agenciatributaria.gob.es/static_files/Sede/Biblioteca/Manual/Practicos/IRPF/IRPF-2025/ManualRenta2025Parte1_es_es.pdf, pages 422-425.

At the original decision baseline, `compute_inventory_variation` returned cents-rounded `closing - opening`, while `compute_anexo_d_inventory_variation` mislabelled that signed value as casilla 0155 and collapsed the two official destinations. Evidence: commit `159465372d`, `src/cadrumo/domain/contribuyente/inventory/__init__.py:322-386`. Commit `900319dd7f` removed that stale destination; commits through `841e4444f8` implemented the split projection.

### The original continuity and closing-authority gaps are resolved

At the original decision baseline, `InventoryLedgerDocument` enforced one ledger per `(actividad_id, year)` but did not enforce prior-closing continuity, and bare `closing_stock` could override derived closing without an authority record. Evidence: commit `159465372d`, `src/cadrumo/domain/contribuyente/inventory/__init__.py:203-293` and `:322-339`. Commits `24a7718153` through `a8f6ab0769` subsequently implemented the grounded closing-authority contract. The remaining blocker is how those already authoritative activity rows are represented in registry resolution.

### Missing source state cannot become a zero declaration

The official form distinguishes the three values; it does not establish that absence of an application ledger proves they are zero. At the original baseline, the readiness declaration said inventory was not yet a calculation source and emitted no resolution diagnostics. Evidence: commit `159465372d`, `src/cadrumo/application/inventory/_source_readiness.py:1-51`, and `2026-08-22-modelo-work-binding-architecture-inventory-gap-verification-reference`. Commits through `8c1514031d` subsequently enrolled the resolver and ownership/refusal behavior; the activity-row carrier must preserve those failure semantics rather than infer zero.

### Official evidence currently authorizes only the 2025 slice

Local registry roles repeat from 2020 through 2025, but this research directly verified only the 2025 annual form and manual. Repeated identifiers do not prove legal continuity. The first implementation can target 2025; extension to 2020-2024 requires each annual form/manual or a separately grounded continuity rule.

### A literal inventory selector cannot represent taxpayer-specific activity rows

Before S43, the strict selector required one nonblank literal `actividad_id`, the resolver grouped bindings by that literal, and no production M100 inventory binding existed; commit `6315605be8` captures that historical blocker. S43 replaced it with an immutable row-template selector carrying `projection_grain`, `fact`, `record`, `grouping`, `row_field`, and `target_casilla_id`, with no taxpayer activity identity. Production binding `0065-renta-2025-inventory-activity-rows.toml` now declares the three templates, and S176 expands deterministic runtime projections into row values and identities. Current evidence: `src/cadrumo/domain/calculations/registry/_inventory_bindings.py:42-70`, `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025/bindings/0065-renta-2025-inventory-activity-rows.toml:1`, and `src/cadrumo/application/aggregation/_inventory.py:83-183`. The generic immutable hydration boundary remains evidenced by `src/cadrumo/domain/calculations/registry/_schema.py:656-664`, `src/cadrumo/domain/calculations/registry/_schema.py:716-732`, and `src/cadrumo/domain/calculations/registry/_binding_selector_utils.py:525-550`.

The work unit is keyed by bucket, modelo, filing year, period, and registry revision and carries no economic-activity coordinate. The taxpayer's actual activity identifiers instead occur in the encrypted inventory ledger. A static registry activity ID would therefore fabricate filing-instance data; a wildcard or taxpayer-wide sum would discard the exact activity grain established above. Evidence: `src/cadrumo/domain/modelos/_work_unit.py:7-20`, `src/cadrumo/domain/modelos/_work_unit.py:125-168`, and `src/cadrumo/application/aggregation/_inventory.py:118-171`.

### Existing runtime-row mechanisms preserve registry semantics without static activity IDs

The source mesh has a first-class row-indexed carrier keyed by `(BindingId, row_index)`, with exclusive merge and serialization behavior, while its ordinary decimal channel is keyed only by `BindingId`. S170-S175 added the matching typed source-row identity association, encrypted persistence, replay validation, and safe-output redaction. Existing row resolvers enumerate canonical runtime observations and emit one value for each binding and 1-based row index. Evidence: `src/cadrumo/application/aggregation/_source_mesh.py:839-853`, `src/cadrumo/application/aggregation/_source_mesh.py:930-966`, `src/cadrumo/application/aggregation/_source_mesh.py:1168-1171`, `src/cadrumo/domain/modelos/_calculation_revision.py:962-979`, and `src/cadrumo/domain/calculations/registry/_detail_record_bindings.py:668-677`. The accepted M720 row-carrier decision rejects synthetic scalar IDs and unrelated detail-row DTO reuse in favor of this structured coordinate: `2026-07-05-modelo-720-row-carrier-adr`.

M303 provides a complementary typed-row precedent: runtime activity rows carry durable `activity_id` values, and projection selects an exact matching immutable calculation activity rather than consuming an undifferentiated scalar. M349 demonstrates immutable row-template semantics and runtime field suppression through the row's active binding set. Evidence: `src/cadrumo/domain/iva/_regimen_simplificado_rows.py:268-303`, `src/cadrumo/domain/calculations/registry/_m303_regimen_simplificado_projection.py:248-266`, `src/cadrumo/domain/prorrata_register/__init__.py:181-198`, `src/cadrumo/application/filing/_record_renderer.py:232-243`, and `src/cadrumo/application/filing/_record_field_renderer.py:157-162`.

The alternatives are a literal binding per activity, a wildcard followed by a taxpayer-wide fold, a new inventory-only carrier, or registry templates expanded into the existing row-indexed channel from encrypted ledger activity rows. Literal bindings cannot know taxpayer activity identities at registry-authoring time; wildcard folding violates the official grain; a separate carrier duplicates a source-mesh capability already accepted for M720; and the existing row carrier needs an additional identity association because position is not source identity. Scalar formula consumption is outside the present carrier evidence: the accepted M720 decision limits row values to draft, replay, and export pending separate adjudication.

### Row binding transport does not materialise row casillas or make M100 exportable

The application persists resolved row bindings as a nested `BindingId -> row_index -> value` map and replays that map into the binding-input surface. `CalculationRevision` stores both `row_binding_values` and their source identities, but its computed `casilla_values` remain a separate scalar `CasillaId -> Decimal` map. Evidence: `src/cadrumo/application/modelo/_calculation_resolution.py:250-280`, `src/cadrumo/application/modelo/_revision_persistence.py:244-255`, `src/cadrumo/application/modelo/_revision_persistence.py:359-373`, `src/cadrumo/application/modelo/_revision_replay_inputs.py:98-108`, and `src/cadrumo/domain/modelos/_calculation_revision.py:962-979`.

The registry engine accepts only scalar `binding_values`; `resolve_bound_casilla_values` projects only that scalar map into bound casillas. Row-indexed values are therefore never mapped to casilla coordinates or evaluated as per-row formula inputs. For a bound casilla whose source is not in the special observation-backed set, missing scalar input follows the ordinary `inputs.get(casilla.id, 0)` path, so linking an inventory row binding without row materialisation can yield a zero scalar while the real row values survive only in revision metadata. Evidence: `src/cadrumo/domain/calculations/registry/_formula_runtime.py:340-353`, `src/cadrumo/domain/calculations/registry/_bindings.py:606-640`, and `src/cadrumo/domain/calculations/registry/_formula_initial_values.py:313-351`.

There is also an earlier type failure: filing draft assembly unions every bound-casilla binding into `calculation_binding_ids`, classifies the remainder as decimal, and passes matching inputs to `_decimal_inputs_for_ids`. A ROWS binding linked directly to a bound casilla therefore sends its row-index mapping toward `Decimal(...)` before row preservation can help. Evidence: `src/cadrumo/application/filing/__init__.py:390-413`, `src/cadrumo/application/filing/__init__.py:675-683`, and `src/cadrumo/application/filing/__init__.py:807-818`.

M100 2025 declares one XML-dictionary export layout and no `binding_rows` or activity-row record definition. The generic fixed-width filing renderer can repeat a registry record declared with `repeat = "binding_rows"`, but that constraint shape is not substitutable for nested XML elements. Evidence: `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025/export_layouts/0001-modelo-100-2025-xml-dictionary.toml:1-20`, `src/cadrumo/application/filing/_record_renderer.py:103-127`, and `src/cadrumo/application/filing/_record_renderer.py:159-176`.

The materialisation alternatives are to flatten or sum activity rows into the scalar engine, keep row bindings as review-only metadata, add a typed row-indexed casilla channel, or create an inventory-specific calculation/export bypass. Flattening loses the legally required activity grain; metadata-only transport cannot populate or export the filing; and a source-specific bypass would duplicate registry calculation and layout authority. A row-indexed casilla channel preserves `(CasillaId, row_index)` independently of the binding carrier, but it requires registry-owned direct row-target rules, identity/cohort parity, revision persistence, and a grounded M100 activity export/PDF representation. The inspected evidence supplies neither a per-row formula contract nor a cross-row reduction rule, and the current registry does not establish the exact official XML activity path or PDF row geometry.

### The official XML is row-capable, but inventory alone cannot author its required activity envelope

AEAT's 2025 XSD declares `/Declaracion/DatosEconomicos/TomaDatosAmpliada/RegEstimaDirecta/ActividadEstDirecta` with `minOccurs="0"` and `maxOccurs="6"`. Within each repeated activity, `E1II7`, `E1G1`, and `E1G2` are optional single positive-amount elements. The declaration dictionary maps those exact children to casillas 0177, 0181, and 0182. XML is therefore a grounded row-capable filing format with a six-row bound; the data-entry-only `VariacionExistencias` coordinates are not filed casillas and are not substitutes. Evidence: `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_100/files/03-100-esquema-xsd-ejercicio-2025-actualizado-24-06-2026-793-kb-ejecutable.xsd:5150`, `:5213`, `:5217`, and `:5218`; `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_100/files/01-100-diccionario-declaracion-individual-ejercicio-2025-actualizado-14-04-2026-416-kb-otros-fi.properties:278`, `:282`, and `:283`; and the current AEAT publication page and artifacts listed in Sources.

The same XSD requires `TACT` once in every `ActividadEstDirecta`. The inventory ledger supplies an opaque local `actividad_id`, not the official activity type, IAE epigraph, estimation modality, or declaration-holder coordinate. The existing `TipoActividad` is the canonical closed A01-A05/B01-B05 taxonomy and must be reused, but no production source currently supplies a durable `actividad_id -> activity envelope` join. M303 filing-instance activity evidence has a different model-specific constraint shape and is not substitutable. Rendering only the three inventory amounts would therefore create invalid XML; interpreting `actividad_id` as `TACT` or IAE would fabricate filing data. Evidence: the XSD at `:5150-5175`; `src/cadrumo/core/_tipos_actividad.py:53-100`; `src/cadrumo/application/aggregation/_inventory.py:118-171`; and `src/cadrumo/domain/modelos/_calculation_revision_m303_evidence.py`.

The current XML writer collapses same-path entries into the first matching child: it constructs one scalar `CasillaId -> value` map, walks each dictionary entry once, and `_set_xml_dictionary_path` reuses the first same-tag element. The XML parser already traverses repeated nodes and should be extended rather than reauthored, but export parity is still scalar and cannot prove row coordinates. Evidence: `src/cadrumo/application/filing/_export_xml_dictionary.py:139-157`, `:783-815`; `src/cadrumo/application/filing/_export_parse.py`; and `src/cadrumo/application/filing/_export.py:1525`.

PDF is not an outbound filing format in the current architecture: `ExportLayoutFormat` contains fixed-width and XML dictionary only, and the M100 PDF profiles are inbound extraction surfaces. The BOE form establishes per-activity visual semantics but not a machine-readable repetition/page geometry, while AEAT describes the generated preview PDF as consultation-only. The evidence consequently supports one XML-specific renderer and row-aware XSD proof after a separately grounded complete activity-envelope join, and supports no PDF renderer. Evidence: `src/cadrumo/core/_export_layout_format.py:38-54`; `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025/export_layouts/0001-modelo-100-2025-xml-dictionary.toml:1-20`; https://sede.agenciatributaria.gob.es/Sede/ayuda/consultas-informaticas/renta-ayuda-tecnica/presentar-declaracion-mediante-fichero-generado-externo.html; and Orden HAC/277/2026, Annex I page 27.

This research did not adjudicate production-cost composition, write-model changes, earlier annual revisions, estimation-objective activities, or accounting outside Modelo 100 direct estimation.

## Sources

- https://www.boe.es/eli/es/o/2026/03/25/hac277/dof/spa/pdf
- https://sede.agenciatributaria.gob.es/static_files/Sede/Biblioteca/Manual/Practicos/IRPF/IRPF-2025/ManualRenta2025Parte1_es_es.pdf
- https://sede.agenciatributaria.gob.es/Sede/ayuda/disenos-registro/modelos-100-199.html
- https://sede.agenciatributaria.gob.es/static_files/Sede/Disenyo_registro/DR_100_199/Renta2025.xsd
- https://sede.agenciatributaria.gob.es/static_files/Sede/Disenyo_registro/DR_100_199/diccionarioXSD_2025.properties
- https://sede.agenciatributaria.gob.es/Sede/ayuda/consultas-informaticas/renta-ayuda-tecnica/presentar-declaracion-mediante-fichero-generado-externo.html
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_100/files/03-100-esquema-xsd-ejercicio-2025-actualizado-24-06-2026-793-kb-ejecutable.xsd:5150`
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_100/files/03-100-esquema-xsd-ejercicio-2025-actualizado-24-06-2026-793-kb-ejecutable.xsd:5213`
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_100/files/03-100-esquema-xsd-ejercicio-2025-actualizado-24-06-2026-793-kb-ejecutable.xsd:5217`
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_100/files/03-100-esquema-xsd-ejercicio-2025-actualizado-24-06-2026-793-kb-ejecutable.xsd:5218`
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_100/files/01-100-diccionario-declaracion-individual-ejercicio-2025-actualizado-14-04-2026-416-kb-otros-fi.properties:278`
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_100/files/01-100-diccionario-declaracion-individual-ejercicio-2025-actualizado-14-04-2026-416-kb-otros-fi.properties:282`
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_100/files/01-100-diccionario-declaracion-individual-ejercicio-2025-actualizado-14-04-2026-416-kb-otros-fi.properties:283`
- `src/cadrumo/core/_tipos_actividad.py:53-100`
- `src/cadrumo/core/_export_layout_format.py:38-54`
- `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025/casillas/c0177.toml:1`
- `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025/casillas/c0181.toml:1`
- `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025/casillas/c0182.toml:1`
- `src/cadrumo/domain/contribuyente/inventory/__init__.py:89-148`
- `src/cadrumo/domain/contribuyente/inventory/__init__.py:203-293`
- `src/cadrumo/domain/contribuyente/inventory/__init__.py:322-386`
- `src/cadrumo/domain/contribuyente/inventory/__init__.py:406-476`
- `src/cadrumo/application/inventory/_source_readiness.py:1-51`
- `src/cadrumo/domain/calculations/registry/_inventory_bindings.py:42-69`
- `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025/bindings/0065-renta-2025-inventory-activity-rows.toml:1`
- `src/cadrumo/application/aggregation/_inventory.py:118-171`
- `src/cadrumo/domain/calculations/registry/_schema.py:656-664`
- `src/cadrumo/domain/calculations/registry/_schema.py:716-732`
- `src/cadrumo/domain/calculations/registry/_binding_selector_utils.py:525-550`
- `src/cadrumo/domain/modelos/_work_unit.py:7-20`
- `src/cadrumo/domain/modelos/_work_unit.py:125-168`
- `src/cadrumo/application/aggregation/_source_mesh.py:839-853`
- `src/cadrumo/application/aggregation/_source_mesh.py:930-966`
- `src/cadrumo/application/aggregation/_source_mesh.py:1168-1171`
- `src/cadrumo/domain/calculations/registry/_detail_record_bindings.py:668-677`
- `src/cadrumo/domain/iva/_regimen_simplificado_rows.py:268-303`
- `src/cadrumo/domain/calculations/registry/_m303_regimen_simplificado_projection.py:248-266`
- `src/cadrumo/domain/prorrata_register/__init__.py:181-198`
- `src/cadrumo/application/filing/_record_renderer.py:232-243`
- `src/cadrumo/application/filing/_record_field_renderer.py:157-162`
- `src/cadrumo/application/modelo/_calculation_resolution.py:250-280`
- `src/cadrumo/application/modelo/_revision_persistence.py:244-255`
- `src/cadrumo/application/modelo/_revision_persistence.py:359-373`
- `src/cadrumo/application/modelo/_revision_replay_inputs.py:98-108`
- `src/cadrumo/domain/modelos/_calculation_revision.py:962-979`
- `src/cadrumo/domain/calculations/registry/_formula_runtime.py:340-353`
- `src/cadrumo/domain/calculations/registry/_bindings.py:606-640`
- `src/cadrumo/domain/calculations/registry/_formula_initial_values.py:313-351`
- `src/cadrumo/application/filing/__init__.py:390-413`
- `src/cadrumo/application/filing/__init__.py:675-683`
- `src/cadrumo/application/filing/__init__.py:807-818`
- `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025/export_layouts/0001-modelo-100-2025-xml-dictionary.toml:1-20`
- `src/cadrumo/application/filing/_record_renderer.py:103-127`
- `src/cadrumo/application/filing/_record_renderer.py:159-176`
- `2026-07-05-modelo-720-row-carrier-adr`
- `2026-08-22-modelo-work-binding-architecture-inventory-gap-verification-reference`
