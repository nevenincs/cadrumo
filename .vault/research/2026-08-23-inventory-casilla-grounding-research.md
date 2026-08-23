---
tags:
  - '#research'
  - '#inventory-casilla-grounding'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:48e194a8372776b966915d5d45e0036c349aa055b980f052a2f1afb8d27cde3c'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
  - "[[2026-08-22-modelo-work-binding-architecture-inventory-gap-verification-reference]]"
---

# `inventory-casilla-grounding` research: `Modelo 100 stock valuation mapping`

Official 2025 evidence supports a three-output inventory source for each economic activity in direct estimation: purchases go to 0181, a positive closing-minus-opening difference goes to income box 0177, and the magnitude of a negative difference goes to expense box 0182. It does not support forwarding the existing signed “Anexo D 0155” helper. The encrypted ledger has the right activity/year grain and can calculate the two variation branches, but its purchase total is not yet a complete tax acquisition-cost fact when indirect tax is non-recoverable. The mapping ADR must therefore settle a corrected acquisition-cost projection, mutually exclusive variation outputs, supported revision window, explicit absence behavior, and override ownership before implementation.

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
- `2026-08-22-modelo-work-binding-architecture-inventory-gap-verification-reference`
