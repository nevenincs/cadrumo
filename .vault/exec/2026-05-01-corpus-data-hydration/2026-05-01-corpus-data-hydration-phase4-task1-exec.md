---
tags:
  - '#exec'
  - '#corpus-data-hydration'
date: '2026-05-01'
modified: '2026-05-01'
related:
  - "[[2026-05-01-corpus-data-hydration-plan]]"
---

# `corpus-data-hydration` phase-4 task-1: Modelo 200, 202 (Sociedades)

Manual semantic extraction and hydration of Modelo 200 and 202 (Impuesto sobre Sociedades).

## Sourcing
Official AEAT documentation sourced:
- URL: `https://sede.agenciatributaria.gob.es/Sede/ayuda/manuales-videos-folletos/manuales-practicos/sociedades-2024.html`

## Casilla Semantic Mapping (Core Liquidación)

| Casilla | Label (ES) | Help (ES) |
| :--- | :--- | :--- |
| 00550 | Resultado cuenta pérdidas/ganancias | Resultado contable antes de impuestos. |
| 00562 | Base imponible | Base imponible previa a la compensación de bases imponibles negativas. |
| 00582 | Cuota íntegra | Resultado de aplicar el tipo de gravamen a la base imponible. |
| 00592 | Deducciones por doble imposición | Importe de las deducciones para evitar la doble imposición. |
| 00599 | Cuota líquida | Diferencia entre la cuota íntegra y las deducciones. |
| 00611 | Retenciones e ingresos a cuenta | Importe total de las retenciones soportadas por la sociedad. |
| 00621 | Cuota del ejercicio a ingresar/devolver | Resultado final de la autoliquidación. |

## Tasks
- [ ] Update `corpus/casillas/modelo_200/*.json`
- [ ] Update `corpus/casillas/modelo_202/*.json`
