---
tags:
  - '#exec'
  - '#corpus-data-hydration'
date: '2026-05-01'
modified: '2026-05-01'
related:
  - "[[2026-05-01-corpus-data-hydration-plan]]"
---

# `corpus-data-hydration` phase-2 task-2: Modelo 390 (IVA Anual)

Manual semantic extraction and hydration of Modelo 390 (IVA Resumen Anual) for the period 2023-2025.

## Sourcing
Official AEAT documentation sourced:
- URL: `https://sede.agenciatributaria.gob.es/Sede/ayuda/manuales-videos-folletos/manuales-practicos/iva-2025/capitulo-12-declaracion-resumen-anual-modelo-390.html`
- Validated against: Orden HAC/1167/2024.

## Casilla Semantic Mapping (Key Sections)

| Casilla | Label (ES) | Help (ES) |
| :--- | :--- | :--- |
| 01 | Régimen general (Base 4%) | Base imponible gravada al tipo del 4%. |
| 04 | Régimen general (Base 10%) | Base imponible gravada al tipo del 10%. |
| 100 | Régimen general (Base 21%) | Base imponible gravada al tipo del 21%. |
| 33 | Total bases y cuotas devengadas | Suma de todas las bases y cuotas de IVA devengado del ejercicio. |
| 47 | Total cuotas deducibles | Suma de todas las cuotas de IVA deducible del ejercicio. |
| 65 | Resultado régimen general | Diferencia entre la casilla 33 (cuota) y la casilla 47. |
| 84 | Volumen de operaciones | Importe total de las entregas de bienes y prestaciones de servicios realizadas. |
| 95 | IVA importación liquidado ADUANA | Cuotas de IVA a la importación liquidadas por la Aduana pendientes de ingreso. |

## Tasks
- [ ] Update `corpus/casillas/modelo_390/*.json` for 2023, 2024, 2025.
- [ ] Align 2024 schema with the HAC/1167/2024 rate changes.
