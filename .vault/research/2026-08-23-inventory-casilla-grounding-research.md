---
tags:
  - '#research'
  - '#inventory-casilla-grounding'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:3eacc265a410f515a90f6b526c35953f61108932d1aa04b10b1d22b2623a9b4d'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
  - "[[2026-08-22-modelo-work-binding-architecture-inventory-gap-verification-reference]]"
  - '[[2026-07-05-modelo-720-row-carrier-adr]]'
---

# `inventory-casilla-grounding` research: `Modelo 100 stock valuation mapping`

Official 2025 evidence supports three inventory outputs for each direct-estimation economic activity: purchases in 0181, positive closing-minus-opening variation in 0177, and the magnitude of negative variation in 0182. The source-domain gaps found at the original adjudication baseline have since been implemented, but runtime inspection exposes a remaining activity-grain mismatch: immutable registry TOML cannot contain the filing instance's concrete activity identities. Existing row carriers can transport repeated binding values, while their positional key alone does not retain the canonical source-row identity. The mapping ADR must settle the runtime activity-row expansion and identity-preservation boundary.

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

### Grain matches, but continuity and explicit closing authority remain unresolved

At the original decision baseline, `InventoryLedgerDocument` enforced one ledger per `(actividad_id, year)` but did not enforce prior-closing continuity, and bare `closing_stock` could override derived closing without an authority record. Evidence: commit `159465372d`, `src/cadrumo/domain/contribuyente/inventory/__init__.py:203-293` and `:322-339`. Commits `24a7718153` through `a8f6ab0769` subsequently implemented the grounded closing-authority contract. The remaining blocker is how those already authoritative activity rows are represented in registry resolution.

### Missing source state cannot become a zero declaration

The official form distinguishes the three values; it does not establish that absence of an application ledger proves they are zero. At the original baseline, the readiness declaration said inventory was not yet a calculation source and emitted no resolution diagnostics. Evidence: commit `159465372d`, `src/cadrumo/application/inventory/_source_readiness.py:1-51`, and `2026-08-22-modelo-work-binding-architecture-inventory-gap-verification-reference`. Commits through `8c1514031d` subsequently enrolled the resolver and ownership/refusal behavior; the activity-row carrier must preserve those failure semantics rather than infer zero.

### Official evidence currently authorizes only the 2025 slice

Local registry roles repeat from 2020 through 2025, but this research directly verified only the 2025 annual form and manual. Repeated identifiers do not prove legal continuity. The first implementation can target 2025; extension to 2020-2024 requires each annual form/manual or a separately grounded continuity rule.

### A literal inventory selector cannot represent taxpayer-specific activity rows

The current strict selector requires one nonblank `actividad_id`, and the resolver groups bindings by that literal before loading the encrypted ledger at `(actividad_id, 2025)`. `DataBindingDefinition` hydrates the immutable TOML selector directly into its source-family model; neither hydration nor the common selector validator provides runtime interpolation, a wildcard, or a template-substitution phase. No production M100 inventory binding currently supplies an activity identifier; the only concrete examples are synthetic selector tests. Evidence: `src/cadrumo/domain/calculations/registry/_inventory_bindings.py:42-69`, `src/cadrumo/application/aggregation/_inventory.py:118-171`, `src/cadrumo/domain/calculations/registry/_schema.py:656-664`, `src/cadrumo/domain/calculations/registry/_schema.py:716-732`, and `src/cadrumo/domain/calculations/registry/_binding_selector_utils.py:525-550`.

The work unit is keyed by bucket, modelo, filing year, period, and registry revision and carries no economic-activity coordinate. The taxpayer's actual activity identifiers instead occur in the encrypted inventory ledger. A static registry activity ID would therefore fabricate filing-instance data; a wildcard or taxpayer-wide sum would discard the exact activity grain established above. Evidence: `src/cadrumo/domain/modelos/_work_unit.py:7-20`, `src/cadrumo/domain/modelos/_work_unit.py:125-168`, and `src/cadrumo/application/aggregation/_inventory.py:118-171`.

### Existing runtime-row mechanisms preserve registry semantics without static activity IDs

The source mesh already has a first-class row-indexed carrier keyed by `(BindingId, row_index)`, with exclusive merge and serialization behavior, while its ordinary decimal channel is keyed only by `BindingId`. Existing row resolvers enumerate canonical runtime observations and emit one value for each binding and 1-based row index. Evidence: `src/cadrumo/application/aggregation/_source_mesh.py:839-853`, `src/cadrumo/application/aggregation/_source_mesh.py:930-966`, `src/cadrumo/application/aggregation/_source_mesh.py:1168-1171`, and `src/cadrumo/domain/calculations/registry/_detail_record_bindings.py:668-677`. The accepted M720 row-carrier decision rejects synthetic scalar IDs and unrelated detail-row DTO reuse in favor of this structured coordinate: `2026-07-05-modelo-720-row-carrier-adr`.

M303 provides a complementary typed-row precedent: runtime activity rows carry durable `activity_id` values, and projection selects an exact matching immutable calculation activity rather than consuming an undifferentiated scalar. M349 demonstrates immutable row-template semantics and runtime field suppression through the row's active binding set. Evidence: `src/cadrumo/domain/iva/_regimen_simplificado_rows.py:268-303`, `src/cadrumo/domain/calculations/registry/_m303_regimen_simplificado_projection.py:248-266`, `src/cadrumo/domain/prorrata_register/__init__.py:181-198`, `src/cadrumo/application/filing/_record_renderer.py:232-243`, and `src/cadrumo/application/filing/_record_field_renderer.py:157-162`.

The alternatives are a literal binding per activity, a wildcard followed by a taxpayer-wide fold, a new inventory-only carrier, or registry templates expanded into the existing row-indexed channel from encrypted ledger activity rows. Literal bindings cannot know taxpayer activity identities at registry-authoring time; wildcard folding violates the official grain; a separate carrier duplicates a source-mesh capability already accepted for M720; and the existing row carrier needs an additional identity association because position is not source identity. Scalar formula consumption is outside the present carrier evidence: the accepted M720 decision limits row values to draft, replay, and export pending separate adjudication.

### Row binding transport does not materialise row casillas or make M100 exportable

The application persists resolved row bindings as a nested `BindingId -> row_index -> value` map and replays that map into the binding-input surface. `CalculationRevision` stores both `row_binding_values` and their source identities, but its computed `casilla_values` remain a separate scalar `CasillaId -> Decimal` map. Evidence: `src/cadrumo/application/modelo/_calculation_resolution.py:250-280`, `src/cadrumo/application/modelo/_revision_persistence.py:244-255`, `src/cadrumo/application/modelo/_revision_persistence.py:359-373`, `src/cadrumo/application/modelo/_revision_replay_inputs.py:98-108`, and `src/cadrumo/domain/modelos/_calculation_revision.py:962-979`.

The registry engine accepts only scalar `binding_values`; `resolve_bound_casilla_values` projects only that scalar map into bound casillas. Row-indexed values are therefore never mapped to casilla coordinates or evaluated as per-row formula inputs. For a bound casilla whose source is not in the special observation-backed set, missing scalar input follows the ordinary `inputs.get(casilla.id, 0)` path, so linking an inventory row binding without row materialisation can yield a zero scalar while the real row values survive only in revision metadata. Evidence: `src/cadrumo/domain/calculations/registry/_formula_runtime.py:340-353`, `src/cadrumo/domain/calculations/registry/_bindings.py:606-640`, and `src/cadrumo/domain/calculations/registry/_formula_initial_values.py:313-351`.

There is also an earlier type failure: filing draft assembly unions every bound-casilla binding into `calculation_binding_ids`, classifies the remainder as decimal, and passes matching inputs to `_decimal_inputs_for_ids`. A ROWS binding linked directly to a bound casilla therefore sends its row-index mapping toward `Decimal(...)` before row preservation can help. Evidence: `src/cadrumo/application/filing/__init__.py:390-413`, `src/cadrumo/application/filing/__init__.py:675-683`, and `src/cadrumo/application/filing/__init__.py:807-818`.

M100 2025 declares one XML-dictionary export layout and no `binding_rows` or activity-row record definition. The generic filing renderer can repeat only a registry record declared with `repeat = "binding_rows"`; otherwise it renders one scalar record occurrence. Evidence: `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025/export_layouts/0001-modelo-100-2025-xml-dictionary.toml:1-20`, `src/cadrumo/application/filing/_record_renderer.py:103-127`, and `src/cadrumo/application/filing/_record_renderer.py:159-176`.

The materialisation alternatives are to flatten or sum activity rows into the scalar engine, keep row bindings as review-only metadata, add a typed row-indexed casilla channel, or create an inventory-specific calculation/export bypass. Flattening loses the legally required activity grain; metadata-only transport cannot populate or export the filing; and a source-specific bypass would duplicate registry calculation and layout authority. A row-indexed casilla channel preserves `(CasillaId, row_index)` independently of the binding carrier, but it requires registry-owned direct row-target rules, identity/cohort parity, revision persistence, and a grounded M100 activity export/PDF representation. The inspected evidence supplies neither a per-row formula contract nor a cross-row reduction rule, and the current registry does not establish the exact official XML activity path or PDF row geometry.

This research did not adjudicate production-cost composition, write-model changes, earlier annual revisions, estimation-objective activities, or accounting outside Modelo 100 direct estimation.

## Sources

- https://www.boe.es/eli/es/o/2026/03/25/hac277/dof/spa/pdf
- https://sede.agenciatributaria.gob.es/static_files/Sede/Biblioteca/Manual/Practicos/IRPF/IRPF-2025/ManualRenta2025Parte1_es_es.pdf
- `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025/casillas/c0177.toml:1`
- `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025/casillas/c0181.toml:1`
- `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025/casillas/c0182.toml:1`
- `src/cadrumo/domain/contribuyente/inventory/__init__.py:89-148`
- `src/cadrumo/domain/contribuyente/inventory/__init__.py:203-293`
- `src/cadrumo/domain/contribuyente/inventory/__init__.py:322-386`
- `src/cadrumo/domain/contribuyente/inventory/__init__.py:406-476`
- `src/cadrumo/application/inventory/_source_readiness.py:1-51`
- `src/cadrumo/domain/calculations/registry/_inventory_bindings.py:42-69`
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
