---
tags:
  - '#exec'
  - '#corpus-data-hydration'
date: '2026-05-01'
modified: '2026-05-01'
related:
  - "[[2026-05-01-corpus-data-hydration-plan]]"
---

# `corpus-data-hydration` phase-1 task-2: Modelo 131 (IRPF Módulos)

Manual semantic extraction and hydration of Modelo 131 (IRPF Estimación Objetiva) for the period 2023-2026.

## Sourcing
Official AEAT documentation sourced:
- URL: `https://sede.agenciatributaria.gob.es/Sede/ayuda/manuales-videos-folletos/manuales-practicos/irpf-2025/capitulo-18-gestion-impuesto/pago-fraccionado/instrucciones-cumplimentacion-modelo-131.html`
- Validated against: Orden HAC/1347/2024.

## Casilla Semantic Mapping (Core)

| Casilla | Label (ES) | Help (ES) |
| :--- | :--- | :--- |
| 01 | Rendimiento neto (Actividad 1) | Rendimiento neto resultante de la aplicación de los signos, índices o módulos (Actividad 1). |
| 02 | Retenciones soportadas (Actividad 1) | Retenciones e ingresos a cuenta soportados (Actividad 1). |
| 03 | Pago fraccionado (Actividad 1) | Resultado de aplicar el porcentaje al rendimiento neto minorado (Actividad 1). |
| 10 | Suma de pagos fraccionados | Suma de los pagos fraccionados de todas las actividades. |
| 12 | Minoración Art. 80 bis | Importe de la minoración por aplicación de la deducción del artículo 80 bis. |
| 15 | Resultados negativos anteriores | Importe de los resultados negativos de trimestres anteriores del mismo ejercicio. |
| 19 | Resultado final | Resultado de la autoliquidación a ingresar o devolver. |

## Tasks
- [ ] Update `corpus/casillas/modelo_131/*.json` for 2023-2026.
- [ ] Ensure all casillas required by the extractor are hydrated.
