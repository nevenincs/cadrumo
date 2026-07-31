---
tags:
  - '#exec'
  - '#corpus-data-hydration'
date: '2026-05-01'
modified: '2026-07-17'
body_hash: 'sha256:41785753f905fd1cf2b8fdf71603563ca6151e9aa4ddddbf56cb19fb5759f6d6'
related:
  - "[[2026-05-01-corpus-data-hydration-plan]]"
---

# `corpus-data-hydration` phase-3 task-2: Modelo 115 (Alquileres)

Manual semantic extraction and hydration of Modelo 115 (Retenciones sobre alquileres) for the period 2023-2026.

## Sourcing
Official AEAT documentation sourced:
- URL: `https://sede.agenciatributaria.gob.es/Sede/ayuda/manuales-videos-folletos/manuales-practicos/irpf-2025/capitulo-18-gestion-impuesto/retenciones-ingresos-cuenta/instrucciones-cumplimentacion-modelo-115.html`
- Validated against: Orden HAP/2194/2013.

## Casilla Semantic Mapping (All)

| Casilla | Label (ES) | Help (ES) |
| :--- | :--- | :--- |
| 01 | N.º perceptores | Número de personas o entidades (arrendadores) a quienes se han satisfecho rentas por alquiler. |
| 02 | Base de las retenciones | Importe total de la base de las retenciones e ingresos a cuenta (importe bruto del alquiler). |
| 03 | Retenciones e ingresos a cuenta | Importe total de las retenciones e ingresos a cuenta practicados en el periodo (normalmente el 19%). |
| 04 | A deducir (Complementaria) | Exclusivamente en caso de autoliquidación complementaria: resultados de declaraciones anteriores. |
| 05 | Resultado a ingresar | Resultado final de la liquidación (casilla 03 - casilla 04). |

## Tasks
- [ ] Update `corpus/casillas/modelo_115/*.json` for 2023-2026.
- [ ] Verify using `aeat casillas verify`.
