---
tags:
  - '#reference'
  - '#ledger-renta-pipeline'
date: '2026-05-08'
modified: '2026-05-08'
related:
  - "[[2026-05-08-ledger-renta-pipeline-plan]]"
  - "[[2026-05-08-ledger-renta-pipeline-adr]]"
  - "[[2026-05-08-ledger-renta-pipeline-research]]"
---



# `ledger-renta-pipeline` reference: `modeller-input-inventory`

Phase 1 inventory of modeller inputs that can receive ledger-derived
data, and of inputs that should remain manual, relation-driven, or
previous-filing-driven.

Sources consulted include the calculation registry JSON payloads,
binding resolver functions, declaration CLI aggregation entrypoint,
transaction catalogue domain, invoice catalogue domain, and Renta
deductible spending category profiles.

## Findings

### Registry Binding Coverage

Current registry binding source kinds are unevenly distributed:

| Modelo | Current binding source kinds | Ledger integration status |
| --- | --- | --- |
| 100 | `manual_input`, `profile`, `previous_filing` | No direct ledger binding exists. Direct-estimation expense linkage is new work. |
| 130 | `previous_filing` | Casillas `01` and `02` are manual today but are strong ledger-derived candidates. |
| 303, 322, 353, 390 | `ledger_iva_aggregation` | Binding schema and resolver exist; missing CLI repository aggregation adapter. |
| 309 | `ledger_iva_aggregation` | Binding schema and resolver exist for limited IVA self-assessment inputs. |
| 369 | `ledger_oss_aggregation` | Binding schema and resolver exist for OSS/IOSS examples. |
| 111, 115, 123 | none | These retention models are not direct Renta ledger inputs in this phase. |
| 180, 190, 193 | `previous_filing` | Annual retention summaries feed Renta through relations, not direct ledger injection. |

The public resolver surface already includes
`resolve_bound_casilla_inputs`, `resolve_previous_filing_binding_values`,
`resolve_invoice_binding_values`,
`resolve_ledger_iva_aggregation_binding_values`, and
`resolve_ledger_oss_aggregation_binding_values`. There is no
equivalent Renta expense resolver and no repository-backed adapter from
`TransactionCatalogueRepository` or `InvoiceCatalogueRepository` into
declaration aggregation. `_aggregate_filing_inputs` currently returns an
empty mapping.

### Modelo 100 Direct Estimation

Modelo 100 2025 direct-estimation casillas split into four groups:

| Casilla range | Current role | Ledger treatment |
| --- | --- | --- |
| `0171`-`0179` | Manual computable income inputs | Potential future sales/income bridge. Not part of the first expense slice because `SpendingCategory` is expense-oriented. |
| `0180` | Computed total income | Must remain formula-driven. |
| `0181`-`0217`, `0227` | Manual expense inputs | Primary Renta ledger candidates after legal category-to-casilla mapping. |
| `0218`, `0220`-`0224`, `0226`, `0231`, `0235` | Computed totals and net yields | Must remain formula-driven and consume explicit inputs only. |
| `0219`, `0225`, `0232`-`0234` | Provisions and reductions | Keep manual or separately modelled until legal/evidence contract is designed. |

Candidate expense mappings, not yet implemented and not legally
finalized:

| Existing category/profile area | Candidate Modelo 100 casilla | Notes |
| --- | --- | --- |
| `cuotas_autonomos_ss` | `0186` | Strong first-slice candidate because the casilla label is direct. |
| `mutualidad_alternativa` | `0195` | Requires statutory-cap evaluation. |
| `manutencion_dietas_nacional`, `manutencion_dietas_extranjero` | `0191` | Requires statutory-cap, per-day, and overnight rules. |
| `arrendamiento_local`, `arrendamiento_vivienda_afecto` | `0192` | Home/premises proportionality must be preserved. |
| `reparaciones_conservacion` | `0193` | Direct category alignment. |
| `suministros_home_office_*`, client-direct utilities | `0194` or `0198` | Requires official label/legal decision before binding. |
| `asesoria_contable`, `asesoria_fiscal`, `asesoria_juridica` | `0199` | Strong first-slice candidate. |
| `seguros_responsabilidad_civil`, `seguros_salud_autonomo` | `0200` | Health insurance cap must be modelled. |
| `gastos_bancarios`, `gastos_financieros` | `0203` | Strong first-slice candidate. |
| `tributos_fiscalmente_deducibles` | `0206` | Needs exclusion of non-deductible taxes. |
| `hardware_amortizable`, `mobiliario_amortizable` | `0208` | Requires amortization/asset bridge rather than raw transaction sum. |
| `software_suscripcion`, `publicidad_marketing`, `formacion_profesional`, travel, telecoms | likely `0202`, sometimes amortization-specific | Requires legal projection model and possible subtyping. |
| Non-deductible input VAT | `0205` only when legally non-deductible | Must reconcile with IVA models to avoid double counting deductible input VAT. |

The Renta calculation runtime should not load repositories. The bridge
should aggregate persisted facts into typed filing inputs before
`calculate_registry_snapshot` executes.

### Modelo 130 Direct Estimation

Modelo 130 is a quarterly direct-estimation surface:

| Casilla | Current role | Ledger treatment |
| --- | --- | --- |
| `01` | Manual income | Strong ledger/invoice income candidate. |
| `02` | Manual expense | Strong ledger-derived expense candidate using the same deductible observation substrate as Modelo 100. |
| `03`, `04`, `07`, `12`, `14`, `17`, `19` | Computed | Must remain formula-driven. |
| `05`, `06`, `10`, `15`, `16`, `18` | Prior amounts, retentions, deductions, corrections | Keep manual or relation-driven until separate source contracts exist. |
| `08`-`11` | Agrarian branch | Only ledger-derived if agrarian income source classification is implemented. |

Modelo 130 also has a previous-filing binding
`irpf.previous_year_economic_activity_net_income` that reads prior-year
Modelo 100 casillas `0224`, `1479`, `1553`, and `1577`. That binding
should remain `previous_filing`, not ledger-derived.

### IVA And OSS/IOSS

IVA and OSS/IOSS already have ledger aggregation binding shapes and
resolver functions. Current coverage includes:

| Modelo | Existing ledger aggregation examples |
| --- | --- |
| 303, 322, 353, 390 | Domestic general/reduced/super-reduced repercutido, domestic soportado interiores, and intra-community autorepercutido. |
| 309 | Intra-community autorepercutido and recargo-equivalencia examples. |
| 369 | Union, external, and import OSS/IOSS examples for selected destination/service/goods axes. |

The missing piece is not a new formula. It is repository-backed
declaration aggregation that loads invoice/ledger observations and
passes them into existing binding resolution.

### Retentions And Prior Filings

Modelo 100 2025 relation-driven inputs should stay relation-driven:

| Source modelo | Source output | Target meaning |
| --- | --- | --- |
| 111 | `28` | Work/activity/prize retentions. |
| 115 | `03` | Urban rental retentions. |
| 123 | `09` | Movable capital retentions. |
| 130 | `19` | Direct-estimation fractional payments. |
| 131 | `15` | Objective-estimation fractional payments. |
| 180 | `decl.retenciones-total` | Annual urban rental retention summary. |
| 190 | `decl.retenciones-total` | Annual work/activity/prize retention summary. |
| 193 | `decl.retenciones-total` | Annual movable capital retention summary. |

Ledger linkage for upstream retention models may be valid later, but
Modelo 100 should consume their filed values through relation or
previous-filing mechanisms.

### Required Observation Contract

Phase 2 should define a strict Renta observation contract before code
implementation. Required fields:

- Stable source identifiers: transaction id, invoice id, catalogue id,
  and optional source row/evidence id.
- Date axes: operation date, invoice date, posting date, payment date,
  and the filing-period axis selected for the binding.
- Monetary axes: gross amount, taxable base, IVA amount, deductible
  amount, non-deductible amount, sign, currency, and correction/refund
  marker.
- Classification axes: transaction direction, `SpendingCategory`,
  category family, business classification, proportionality kind,
  business-use ratio, statutory-cap bucket, and legal profile year.
- Projection axes: target modelo, target casilla, aggregation key,
  source-kind name, and provenance explaining why the projection is
  permitted.
- Review axes: classification confidence, reviewed/unreviewed state,
  review actor/timestamp, and reconciliation status with invoice links.

### Implementation Priority

The narrowest reliable first implementation slice is Modelo 100
direct-estimation expenses with unambiguous category-to-casilla
bindings, such as `cuotas_autonomos_ss` to `0186`,
`asesoria_*` to `0199`, `gastos_financieros` or `gastos_bancarios` to
`0203`, and `arrendamiento_local` to `0192`.

That slice still requires Phase 2 decisions on source-kind naming,
observation shape, invoice/transaction precedence, duplicate
prevention, period semantics, sign/refund handling, and legal reference
requirements.
