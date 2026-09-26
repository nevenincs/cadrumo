---
tags:
  - '#research'
  - '#assets-core'
date: '2026-09-21'
modified: '2026-09-21'
body_schema: 'body-v2'
body_hash: 'sha256:e89257afba1cded39c0df96a0f2c59554438ab07d03e1ef145f75f264e761e0a'
related:
  - "[[2026-08-23-amortization-casilla-grounding-research]]"
---

# `assets-core` research: `IRPF asset lifecycle and filing integration options`

The accepted 2025 Modelo 100 authority does not settle asset identity, claim
history, Modelo 130 ownership, or a purchased home's allocation shape. Official
requirements and live code favor a separate IRPF asset linked to acquisition
evidence, append-only claims distinct from forecasts, one schedule projected to
annual and cumulative consumers, and explicit home allocation facts. The ADR
must choose the exact contracts.

## Findings

### Asset identity must preserve evidence without merging tax domains

AEAT requires annual per-asset depreciation charges, while IVA capital-goods
regularization is distinct. An IVA extension cannot represent every non-IVA
purchase or separate depreciable construction from land. A distinct IRPF asset
linked to the canonical acquisition fits the independent legal lifecycles
better than either a universal asset record or an IVA-record extension.

### Forecast schedules and recorded claims need distinct revision semantics

Depreciation starts at readiness for operation and prior accumulated charges
limit the remaining base. Unknown opening history cannot be zero. A mutable
schedule cannot reconstruct prior claims, while filing snapshots alone cannot
represent pre-onboarding history. Immutable asset revisions plus separately
recorded claims tied to calculation or filing provenance cover both needs.

### One schedule should project quarterly cumulative and annual amounts

Modelo 130 casilla 02 includes depreciation from year start through quarter
end; Modelo 100 consumes the annual activity result. Separate calculators risk
drift and manual period entries cannot prove automation. A single schedule can
expose increments, year-to-date totals, and annual totals without summing
cumulative quarters.

### Mixed-use homes require construction, land, ownership, and area facts

Building depreciation excludes land, and partial business affectation applies
to the separately usable business portion subject to ownership conditions. A
generic percentage loses the land and ownership basis; a home-only calculator
duplicates the schedule. Typed allocation components can preserve one schedule
while refusing missing or contradictory facts.

### Service-window day count is an explicit calendar-year proportion

Normal and simplified direct estimation use different tables. Qualifying new
tangible units no greater than EUR 300 may use free depreciation subject to the
EUR 25,000 tax-period limit and its conditions. These are authority and
eligibility inputs, not identity choices. AEAT's investment-book FAQ states that
a quarterly entry distributes the annual resulting charge by multiplying it by
days in use during the applicable period divided by days in that calendar year,
using start-of-use and disposal dates. The implementation can therefore derive
claims and period, year-to-date, and partial-year annual projections directly
from the annual charge using actual calendar days, including 366-day years. The
service window includes the in-service date and excludes the first
out-of-service date, so each day belongs to at most one claim interval.
Canonical euro cents rounding is applied only to emitted period, annual,
remaining-basis, and claim amounts; the ratio and intermediate schedule
arithmetic remain exact Decimal values. The final charge is capped to the
unamortized lawful base.

This evidence supports common-regime direct normal and simplified estimation
for tax year 2025 only. It includes material and intangible assets under their
respective 2025 authority; other years, objective estimation, foral regimes,
and special incentives without enrolled authority remain unsupported.

## Sources

https://sede.agenciatributaria.gob.es/Sede/eu_es/ayuda/manuales-videos-folletos/manuales-practicos/irpf-2025/c07-rendimientos-actividades-economicas-estimacion-directa/fase-1-determinacion-rendimiento-neto/amortizaciones-dotaciones-ejercicio-fiscalmente-deducibles/requisitos-generales.html

https://sede.agenciatributaria.gob.es/Sede/eu_es/ayuda/manuales-videos-folletos/manuales-practicos/irpf-2025/c07-rendimientos-actividades-economicas-estimacion-directa/fase-1-determinacion-rendimiento-neto/amortizaciones-dotaciones-ejercicio-fiscalmente-deducibles/reglas-amortizacion.html

https://sede.agenciatributaria.gob.es/Sede/eu_es/ayuda/manuales-videos-folletos/manuales-practicos/irpf-2025/c07-rendimientos-actividades-economicas-estimacion-directa/fase-1-determinacion-rendimiento-neto/amortizaciones-dotaciones-ejercicio-fiscalmente-deducibles/supuestos-libertad-amortizacion/libertad-amortizacion-supuestos-contemplados-articulo-12_3.html

https://sede.agenciatributaria.gob.es/Sede/eu_es/ayuda/manuales-videos-folletos/manuales-practicos/irpf-2025/c06-rendimientos-actividades-economicas-cuestiones-generales/elementos-patrimoniales-afectos-actividad-economica/criterios-afectacion-bienes-derechos-ejercicio.html

https://www.boe.es/buscar/act.php?id=BOE-A-2015-7771

https://sede.agenciatributaria.gob.es/Sede/impuestos-tasas/impuesto-sobre-renta-personas-fisicas/modelo-130-irpf______esionales-estimacion-directa-fraccionado_/instrucciones.html

https://sede.agenciatributaria.gob.es/Sede/iva/facturacion-registro/preguntas-frecuentes/libro-registro-bienes-inversion-iva-irpf.html

`src/cadrumo/domain/transactions/models.py:89`

`src/cadrumo/application/aggregation/renta_gasto_ledger.py:154`

`src/cadrumo/core/money/rounding.py:1`
