---
tags:
  - '#exec'
  - '#corpus-data-hydration'
date: '2026-05-01'
modified: '2026-05-01'
related:
  - "[[2026-05-01-corpus-data-hydration-plan]]"
---

# `corpus-data-hydration` phase-3 task-1: Modelo 111 (Retenciones)

Manual semantic extraction and hydration of Modelo 111 (Retenciones e ingresos a cuenta) for the period 2023-2026.

## Sourcing
Official AEAT documentation sourced:
- URL: `https://sede.agenciatributaria.gob.es/Sede/ayuda/manuales-videos-folletos/manuales-practicos/irpf-2025/capitulo-18-gestion-impuesto/retenciones-ingresos-cuenta/instrucciones-cumplimentacion-modelo-111.html`
- Validated against: Orden EHA/586/2011.

## Casilla Semantic Mapping (Core)

| Casilla | Label (ES) | Help (ES) |
| :--- | :--- | :--- |
| 01 | N.º perceptores (Trabajo) | Número total de personas físicas a las que se han satisfecho rendimientos del trabajo. |
| 02 | Importe percepciones (Trabajo) | Suma de las percepciones dinerarias satisfechas por rendimientos del trabajo. |
| 03 | Importe retenciones (Trabajo) | Importe total de las retenciones e ingresos a cuenta practicados sobre rendimientos del trabajo. |
| 07 | N.º perceptores (Actividades) | Número total de perceptores de rendimientos de actividades económicas. |
| 08 | Importe percepciones (Actividades) | Importe de las percepciones dinerarias por actividades económicas. |
| 09 | Importe retenciones (Actividades) | Importe de las retenciones practicadas sobre rendimientos de actividades económicas. |
| 28 | Suma de retenciones | Suma de las casillas 03, 06, 09, 12, 15, 18, 21, 24 y 27. |
| 30 | Resultado a ingresar | Resultado final de la liquidación (casilla 28 - casilla 29). |

## Tasks
- [ ] Update `corpus/casillas/modelo_111/*.json` for 2023-2026.
- [ ] Ensure all 21+ casillas required by the extractor are hydrated.
