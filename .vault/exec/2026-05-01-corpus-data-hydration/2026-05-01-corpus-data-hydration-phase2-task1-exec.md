---
tags:
  - '#exec'
  - '#corpus-data-hydration'
date: '2026-05-01'
modified: '2026-05-01'
related:
  - "[[2026-05-01-corpus-data-hydration-plan]]"
---

# `corpus-data-hydration` phase-2 task-1: Modelo 303 (IVA)

Manual semantic extraction and hydration of Modelo 303 (IVA Autoliquidación) for the period 2023-2026.

## Sourcing
Official AEAT documentation sourced:
- URL: `https://sede.agenciatributaria.gob.es/Sede/ayuda/manuales-videos-folletos/manuales-practicos/iva-2025/capitulo-11-declaracion-autoliquidacion-modelo-303.html`
- Validated against: Orden HAC/819/2024.

## Casilla Semantic Mapping (Core 33)

| Casilla | Label (ES) | Help (ES) |
| :--- | :--- | :--- |
| 01 | Base imponible (4%) | Base imponible gravada al tipo superreducido del 4%. |
| 03 | Cuota (4%) | Cuota de IVA devengada al 4%. |
| 04 | Base imponible (10%) | Base imponible gravada al tipo reducido del 10%. |
| 06 | Cuota (10%) | Cuota de IVA devengada al 10%. |
| 07 | Base imponible (21%) | Base imponible gravada al tipo general del 21%. |
| 09 | Cuota (21%) | Cuota de IVA devengada al 21%. |
| 10 | Adquisiciones intracomunitarias (Base) | Base imponible de adquisiciones intracomunitarias de bienes y servicios. |
| 11 | Adquisiciones intracomunitarias (Cuota) | Cuota de IVA devengada por adquisiciones intracomunitarias. |
| 12 | Inversión del sujeto pasivo (Base) | Base imponible de operaciones con inversión del sujeto pasivo. |
| 13 | Inversión del sujeto pasivo (Cuota) | Cuota de IVA devengada por inversión del sujeto pasivo. |
| 14 | Modificación bases y cuotas | Importe de las modificaciones de bases y cuotas de facturas rectificativas. |
| 15 | Modificación bases y cuotas (Cuota) | Cuota de IVA resultante de las modificaciones de facturas rectificativas. |
| 27 | Total cuota devengada | Suma de todas las cuotas devengadas (03 + 06 + 09 + 11 + 13 + 15 + 18 + 21 + 24 + 26). |
| 28 | Operaciones interiores corrientes (Base) | Base imponible de cuotas soportadas en operaciones interiores corrientes. |
| 29 | Operaciones interiores corrientes (Cuota) | Cuota de IVA deducible en operaciones interiores corrientes. |
| 30 | Operaciones interiores bienes inversión (Base) | Base imponible de cuotas soportadas en adquisiciones de bienes de inversión. |
| 31 | Operaciones interiores bienes inversión (Cuota) | Cuota de IVA deducible en adquisiciones de bienes de inversión. |
| 32 | Importaciones bienes corrientes (Base) | Base imponible de cuotas soportadas en importaciones de bienes corrientes. |
| 33 | Importaciones bienes corrientes (Cuota) | Cuota de IVA deducible en importaciones de bienes corrientes. |
| 34 | Importaciones bienes inversión (Base) | Base imponible de cuotas soportadas en importaciones de bienes de inversión. |
| 35 | Importaciones bienes inversión (Cuota) | Cuota de IVA deducible en importaciones de bienes de inversión. |
| 36 | Adquisiciones intracomunitarias bienes (Base) | Base imponible de cuotas soportadas en adquisiciones intracomunitarias de bienes corrientes. |
| 37 | Adquisiciones intracomunitarias bienes (Cuota) | Cuota de IVA deducible en adquisiciones intracomunitarias de bienes corrientes. |
| 45 | Total a deducir | Suma de todas las cuotas deducibles (29 + 31 + 33 + 35 + 37 + 39 + 41 + 43 + 44). |
| 46 | Resultado régimen general | Diferencia entre la casilla 27 y la casilla 45. |
| 64 | Resultado de la liquidación | Resultado de regularización, cuotas a compensar y otros ajustes. |
| 65 | Porcentaje atribuible a Administración | Porcentaje de participación de la Administración del Estado (normalmente 100%). |
| 66 | Atribuible a la Administración | Importe atribuible a la Administración del Estado (casilla 64 * casilla 65). |
| 67 | IVA a la importación liquidado ADUANA | Importe del IVA a la importación liquidado por la Aduana con ingreso diferido. |
| 69 | Resultado | Resultado final antes de compensaciones (casilla 66 + casilla 67). |
| 71 | Resultado de la autoliquidación | Resultado final a ingresar o devolver (incluyendo compensación de periodos anteriores). |

## Tasks
- [ ] Update `corpus/casillas/modelo_303/*.json` for 2023-2026.
- [ ] Ensure all 33+ casillas required by the extractor are hydrated.
