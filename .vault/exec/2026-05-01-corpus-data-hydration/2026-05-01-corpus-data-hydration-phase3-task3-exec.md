---
tags:
  - '#exec'
  - '#corpus-data-hydration'
date: '2026-05-01'
modified: '2026-05-01'
related:
  - "[[2026-05-01-corpus-data-hydration-plan]]"
---

# `corpus-data-hydration` phase-3 task-3: Modelo 123 (Capital Mobiliario)

Manual semantic extraction and hydration of Modelo 123 (Retenciones sobre rendimientos del capital mobiliario) for the period 2023-2026.

## Sourcing
Official AEAT documentation sourced:
- URL: `https://sede.agenciatributaria.gob.es/Sede/ayuda/manuales-videos-folletos/manuales-practicos/irpf-2025/capitulo-18-gestion-impuesto/retenciones-ingresos-cuenta/instrucciones-cumplimentacion-modelo-123.html`

## Casilla Semantic Mapping

| Casilla | Label (ES) | Help (ES) |
| :--- | :--- | :--- |
| 01 | N.º perceptores | Número total de personas o entidades a quienes se han satisfecho rentas del capital mobiliario. |
| 02 | Base de las retenciones | Importe total de las bases de retención o ingresos a cuenta. |
| 03 | Retenciones e ingresos a cuenta | Importe total de las retenciones e ingresos a cuenta practicados. |
| 04 | A deducir (Complementaria) | Exclusivamente en caso de autoliquidación complementaria. |
| 05 | Resultado a ingresar | Resultado de la liquidación (casilla 03 - casilla 04). |

## Tasks
- [ ] Update `corpus/casillas/modelo_123/*.json` for 2023-2026.
