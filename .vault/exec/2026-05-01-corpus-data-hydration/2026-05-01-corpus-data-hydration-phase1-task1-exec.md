---
tags:
  - '#exec'
  - '#corpus-data-hydration'
date: '2026-05-01'
modified: '2026-05-01'
related:
  - "[[2026-05-01-corpus-data-hydration-plan]]"
---

# `corpus-data-hydration` phase-1 task-1: Modelo 130 (IRPF)

Manual semantic extraction and hydration of Modelo 130 (IRPF Pago Fraccionado) for the period 2023-2026.

## Sourcing
Official AEAT documentation sourced:
- URL: `https://sede.agenciatributaria.gob.es/Sede/ayuda/manuales-videos-folletos/manuales-practicos/irpf-2025/capitulo-18-gestion-impuesto/pago-fraccionado/instrucciones-cumplimentacion-modelo-130.html`
- Validated against: Orden HAC/262/2025.

## Casilla Semantic Mapping (01-19)

| Casilla | Label (ES) | Help (ES) |
| :--- | :--- | :--- |
| 01 | Ingresos íntegros | Suma de los ingresos computables derivados de las actividades económicas en estimación directa. |
| 02 | Gastos deducibles | Suma de los gastos deducibles de las actividades económicas. |
| 03 | Rendimiento neto | Diferencia entre los ingresos íntegros (01) y los gastos deducibles (02). |
| 04 | Pago fraccionado (20%) | El 20 por ciento del rendimiento neto acumulado (casilla 03). |
| 05 | Pagos previos | Importe de los pagos fraccionados ingresados por los trimestres anteriores del mismo ejercicio. |
| 06 | Retenciones soportadas | Importe de las retenciones e ingresos a cuenta soportados acumulados del ejercicio. |
| 07 | Pago fraccionado del trimestre | Diferencia entre la casilla 04 y las casillas 05 y 06 (mínimo 0). |
| 08 | Ingresos (agrícolas/ganaderos) | Ingresos íntegros del trimestre de actividades agrícolas, ganaderas o forestales. |
| 09 | Pago fraccionado (2%) | El 2 por ciento de los ingresos íntegros del trimestre (casilla 08). |
| 10 | Retenciones (agrícolas/ganaderos) | Retenciones e ingresos a cuenta soportados en el trimestre. |
| 11 | Pago fraccionado (agrícolas/ganaderos) | Diferencia entre la casilla 09 y la 10 (mínimo 0). |
| 12 | Suma de pagos fraccionados | Suma de las casillas 07 y 11. |
| 13 | Minoración Art. 80 bis | Importe de la minoración por aplicación de la deducción del artículo 80 bis de la Ley del Impuesto. |
| 14 | Diferencia | Diferencia entre la casilla 12 y la 13 (mínimo 0). |
| 15 | Resultados negativos anteriores | Importe de los resultados negativos de trimestres anteriores del mismo ejercicio. |
| 16 | Deducción vivienda habitual | Importe de la deducción por inversión en vivienda habitual (si se tiene derecho). |
| 17 | Pago fraccionado neto | Diferencia entre la casilla 14 y las casillas 15 y 16. |
| 18 | Resultados de declaraciones previas | A deducir: resultado a ingresar de declaraciones anteriores por el mismo concepto y ejercicio. |
| 19 | Resultado final | Resultado de la autoliquidación (casilla 17 - casilla 18). |

## Tasks
- [ ] Update `corpus/casillas/modelo_130/*.json` for 2023, 2024, 2025, 2026.
- [ ] Verify using `aeat casillas verify`.
