---
tags:
  - '#research'
  - '#inventory-casilla-grounding'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:eeac5d05306e74a9343ae0787e368e88d8e833a472d0eeaef22536c3af671f45'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
  - "[[2026-08-22-modelo-work-binding-architecture-inventory-gap-verification-reference]]"
---

# `inventory-casilla-grounding` research: `Modelo 100 stock valuation mapping`

Official 2025 evidence supports a three-output inventory source for each economic activity in direct estimation: purchases go to 0181, a positive closing-minus-opening difference goes to income box 0177, and the magnitude of a negative difference goes to expense box 0182. It does not support forwarding the existing signed â€œAnexo D 0155â€� helper. The encrypted ledger has the right activity/year grain and can calculate the two variation branches, but its purchase total is not yet a complete tax acquisition-cost fact when indirect tax is non-recoverable. Runtime inspection further shows that a concrete activity identifier cannot live in immutable registry TOML: the registry can own the three operation-to-casilla templates, while encrypted ledger rows must supply the filing instance's activity identities through a repeating carrier. The mapping ADR must therefore also settle runtime activity-row expansion and whether those values use the existing row-indexed binding channel.

## Findings

### The official 2025 form separates purchases and both directions of stock variation

The Modelo 100 direct-estimation activity page lists inventory increase among income, then inventory purchases and inventory decrease among deductible expenses. Their boxes are 0177, 0181, and 0182. Because the page is activity-scoped, the projection grain is one `(taxpayer, filing year, activity)`, not one taxpayer-wide scalar. Orden HAC/277/2026 approves this form for tax year 2025. Evidence: https://www.boe.es/eli/es/o/2026/03/25/hac277/dof/spa/pdf, page 27; `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025/casillas/c0177.toml:1`, `c0181.toml:1`, and `c0182.toml:1` in that directory.

The alternatives are one signed output, three unsigned presentation facts, or a consumption scalar. The official presentation rejects the signed output and consumption scalar as direct destinations: it requires purchases independently and routes variation according to sign. The evidence favors `0177 = max(closing - opening, 0)` and `0182 = max(opening - closing, 0)`, with a mutual-exclusion invariant.

### Purchases are acquisition cost, not always the current IVA-exclusive movement value

The AEAT manual defines inventory purchases as current-goods acquisitions from third parties for earning income. Acquisition price includes directly attributable costs and indirect taxes that are not directly recoverable; deductible input IVA is excluded. Evidence: https://sede.agenciatributaria.gob.es/static_files/Sede/Biblioteca/Manual/Practicos/IRPF/IRPF-2025/ManualRenta2025Parte1_es_es.pdf, pages 424-426.

`MovementRecord.value` and both valuation engines total `quantity * resolved_unit_cost` and describe it as IVA-exclusive. Although the record carries `iva_rate`, `iva_amount`, and `deductible_iva_ratio`, `purchase_value` does not add non-deductible IVA and has no field for freight, insurance, duties, or comparable attributable costs. Evidence: `src/cadrumo/domain/contribuyente/inventory/__init__.py:89-148`, `:406-433`, and `:436-476`. Binding current `purchase_value` directly to 0181 could under-declare acquisition cost. The ADR must choose either an enriched, validated purchase-cost fact or refusal whenever the ledger cannot prove complete acquisition cost; the IVA-exclusive subtotal cannot silently stand in for it.

### Stock variation is closing value minus opening value, split by sign

The AEAT manual defines variation as the difference between opening and closing stocks. Closing above opening is income; opening above closing produces an expense of the difference. It also requires the next period's opening value to equal the prior closing value and accepts acquisition price or production cost, with weighted-average cost and FIFO for homogeneous groups. Evidence: https://sede.agenciatributaria.gob.es/static_files/Sede/Biblioteca/Manual/Practicos/IRPF/IRPF-2025/ManualRenta2025Parte1_es_es.pdf, pages 422-425.

`compute_inventory_variation` already returns cents-rounded `closing - opening`, deriving closing through FIFO or weighted average when no explicit closing value exists. But `compute_anexo_d_inventory_variation` mislabels that signed value as casilla 0155 and collapses the two official destinations. Evidence: `src/cadrumo/domain/contribuyente/inventory/__init__.py:322-386`. The 0155 intent should be replaced, not retained as an alias: current registry authority assigns 0155 to a real-estate calculation.

### Grain matches, but continuity and explicit closing authority remain unresolved

`InventoryLedgerDocument` enforces one ledger per `(actividad_id, year)`, matching the form. It does not enforce prior-closing-to-next-opening continuity, and `closing_stock` may override movement-derived closing without recording why it is authoritative. Evidence: `src/cadrumo/domain/contribuyente/inventory/__init__.py:203-293` and `:322-339`. The ADR must settle whether explicit closing is an operator-confirmed physical count, whether it supersedes derived valuation, and how discontinuity is diagnosed. Duplicate, wrong-year, and unexplained conflicting state must fail closed.

### Missing source state cannot become a zero declaration

The official form distinguishes the three values; it does not establish that absence of an application ledger proves they are zero. The current readiness declaration says inventory is not yet a calculation source and emits no resolution diagnostics. Evidence: `src/cadrumo/application/inventory/_source_readiness.py:1-51` and `2026-08-22-modelo-work-binding-architecture-inventory-gap-verification-reference`. The resolver should emit an actionable missing, incomplete, or unreadable diagnostic and leave values unresolved. A complete ledger owns its outputs against caller replacement; deliberate manual input remains the fallback when no source is connected.

### Official evidence currently authorizes only the 2025 slice

Local registry roles repeat from 2020 through 2025, but this research directly verified only the 2025 annual form and manual. Repeated identifiers do not prove legal continuity. The first implementation can target 2025; extension to 2020-2024 requires each annual form/manual or a separately grounded continuity rule.

### A literal inventory selector cannot represent taxpayer-specific activity rows

The current strict selector requires one nonblank `actividad_id`, and the resolver groups bindings by that literal before loading the encrypted ledger at `(actividad_id, 2025)`. `DataBindingDefinition` hydrates the immutable TOML selector directly into its source-family model; neither hydration nor the common selector validator provides runtime interpolation, a wildcard, or a template-substitution phase. No production M100 inventory binding currently supplies an activity identifier; the only concrete examples are synthetic selector tests. Evidence: `src/cadrumo/domain/calculations/registry/_inventory_bindings.py:42-69`, `src/cadrumo/application/aggregation/_inventory.py:118-171`, `src/cadrumo/domain/calculations/registry/_schema.py:656-664`, `src/cadrumo/domain/calculations/registry/_schema.py:716-732`, and `src/cadrumo/domain/calculations/registry/_binding_selector_utils.py:525-550`.

The work unit is keyed by bucket, modelo, filing year, period, and registry revision and carries no economic-activity coordinate. The taxpayer's actual activity identifiers instead occur in the encrypted inventory ledger. A static registry activity ID would therefore fabricate filing-instance data; a wildcard or taxpayer-wide sum would discard the exact activity grain established above. Evidence: `src/cadrumo/domain/modelos/_work_unit.py:7-20`, `src/cadrumo/domain/modelos/_work_unit.py:125-168`, and `src/cadrumo/application/aggregation/_inventory.py:118-171`.

### Existing runtime-row mechanisms preserve registry semantics without static activity IDs

The source mesh already has a first-class row-indexed carrier keyed by `(BindingId, row_index)`, with exclusive merge and serialization behavior, while its ordinary decimal channel is keyed only by `BindingId`. Existing row resolvers enumerate canonical runtime observations and emit one value for each binding and 1-based row index. Evidence: `src/cadrumo/application/aggregation/_source_mesh.py:839-853`, `src/cadrumo/application/aggregation/_source_mesh.py:930-966`, `src/cadrumo/application/aggregation/_source_mesh.py:1168-1171`, and `src/cadrumo/domain/calculations/registry/_detail_record_bindings.py:668-677`. The accepted M720 row-carrier decision rejects synthetic scalar IDs and unrelated detail-row DTO reuse in favor of this structured coordinate: `2026-07-05-modelo-720-row-carrier-adr`.

M303 provides a complementary typed-row precedent: runtime activity rows carry durable `activity_id` values, and projection selects an exact matching immutable calculation activity rather than consuming an undifferentiated scalar. M349 demonstrates immutable row-template semantics and runtime field suppression through the row's active binding set. Evidence: `src/cadrumo/domain/iva/_regimen_simplificado_rows.py:268-303`, `src/cadrumo/domain/calculations/registry/_m303_regimen_simplificado_projection.py:248-266`, `src/cadrumo/domain/prorrata_register/__init__.py:181-198`, `src/cadrumo/application/filing/_record_renderer.py:232-243`, and `src/cadrumo/application/filing/_record_field_renderer.py:157-162`.

The alternatives are a literal binding per activity, a wildcard followed by a taxpayer-wide fold, a new inventory-only carrier, or registry templates expanded into the existing row-indexed channel from encrypted ledger activity rows. Literal bindings cannot know taxpayer activity identities at registry-authoring time; wildcard folding violates the official grain; and a separate carrier duplicates a source-mesh capability already accepted for M720. The evidence favors runtime row expansion through the compatible existing carrier. Scalar formula consumption remains a separate decision because the accepted M720 carrier deliberately limits row values to draft, replay, and export unless a later decision authorizes a row fold.

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
- `2026-07-05-modelo-720-row-carrier-adr`
- `2026-08-22-modelo-work-binding-architecture-inventory-gap-verification-reference`

