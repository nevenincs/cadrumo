---
tags:
  - '#research'
  - '#retenciones-workflow'
date: '2026-09-24'
modified: '2026-09-24'
body_schema: 'body-v2'
body_hash: 'sha256:ef19bd3ef5ff979471ab3fbf4d191baf4ce3ca34b08446d9f202c9a04549d8f4'
related: []
---

# `retenciones-workflow` research: `Withholding domain grounding`

The domain distinctions a withholding agent's workflow must preserve, as the official AEAT material frames them (researched 2026-09-21). These establish the questions to ground. Rates, bases, exceptions, record keys and temporal rules still have to be grounded in the official revision for each year and regime before an oracle uses them.

## Findings

### The obligation follows relevant payments, not taxpayer kind

Business and professional individuals become withholding agents when they pay income in their activity that is subject to withholding. Being autonomo does not by itself activate every return. Profile declarations, recipient status, exceptions and financial evidence must agree.

### Timing differs between taxes

AEAT describes IRPF withholding as arising when the income is paid; its IS explanation uses an exigibility-or-earlier-payment rule. An invoice date is therefore not a universal withholding-period oracle, and scenarios need invoice and payment dates that cross periods and years.

### Periodic and annual duties are separate

The core pairings are 111/190 and 115/180. The withholding agent must also issue certificates and inform recipients, so an exported file alone does not prove full withholding-agent compliance.

### Zero is not absence

The Modelo 111 instructions distinguish relevant income paid with no withholding due from a period with no relevant income paid. Missing evidence is neither state.

### Rent has exceptions and property detail

Modelo 115 must not activate from any rent-labelled payment. Annual Modelo 180 needs property identity and can require several records for one landlord across properties or contracts, so a distinct-NIF count is not the record count.

### Annual detail is substantive

Modelo 190 uses recipient records with identity, clave and subclave, and the applicable monetary and personal fields. Validate record grouping and control totals, not just quarterly sums. The 2025 logical design is the evidence for 2025, not a fixed year for every run.

### Conditional families stay distinct

Capital-income payments use 123/193, and non-resident withholding uses 216/296 with its own treatment. A withholding percentage on an invoice does not select the family.

## Sources

- https://sede.agenciatributaria.gob.es/Sede/irpf/retenciones-ingresos-cuenta-pagos-fraccionados/retenciones-ingresos-cuenta/personas-entidades-obligadas-retener-efectuar-cuenta.html
- https://sede.agenciatributaria.gob.es/Sede/ayuda/manuales-videos-folletos/manuales-practicos/folleto-actividades-economicas/7-otras-obligaciones-fiscales-retenciones.html
- https://sede.agenciatributaria.gob.es/Sede/irpf/retenciones-ingresos-cuenta-pagos-fraccionados/retenciones-ingresos-cuenta/obligaciones-retenedor.html
- https://sede.agenciatributaria.gob.es/Sede/todas-gestiones/impuestos-tasas/pagos-cuenta/modelo-111-reten_____moniales-imputaciones-renta-autoliquidacion_/instrucciones.html
- https://sede.agenciatributaria.gob.es/Sede/ayuda/manuales-videos-folletos/manuales-practicos/folleto-actividades-economicas/7-otras-obligaciones-fiscales-retenciones/7_3-retenciones-arrendamiento-bienes-inmuebles-180.html
- https://www3.agenciatributaria.gob.es/Sede/impuestos-tasas/declaraciones-informativas/modelo-180-decla_____arrendamiento-inmuebles-urbanos-anual_/preguntas-frecuentes.html
- https://sede.agenciatributaria.gob.es/static_files/Sede/Disenyo_registro/DR_100_199/archivos_25/DISENOS_LOGICOS_190_2025.pdf
- https://sede.agenciatributaria.gob.es/Sede/ayuda/manuales-videos-folletos/manuales-practicos/folleto-actividades-economicas/7-otras-obligaciones-fiscales-retenciones/7_4-retenciones-capital-mobiliario-modelos-193.html
- https://sede.agenciatributaria.gob.es/Sede/no-residentes/irnr-sin-establecimiento-permanente/retenciones-irnr-sin-establecimiento-permanente/modelo-216.html
- https://sede.agenciatributaria.gob.es/Sede/procedimientoini/GI22.shtml
