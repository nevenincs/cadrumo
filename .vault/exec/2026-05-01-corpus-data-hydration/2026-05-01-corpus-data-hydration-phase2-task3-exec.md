---
tags:
  - '#exec'
  - '#corpus-data-hydration'
date: '2026-05-01'
modified: '2026-05-01'
related:
  - "[[2026-05-01-corpus-data-hydration-plan]]"
---

# `corpus-data-hydration` phase-2 task-3: Modelo 347, 349, 369 (VIES)

Manual semantic extraction and hydration of Modelo 347, 349, and 369.

## Sourcing
Official AEAT documentation sourced:
- Modelo 347: `https://sede.agenciatributaria.gob.es/Sede/ayuda/manuales-videos-folletos/manuales-practicos/iva-2025/capitulo-13-obligaciones-formales-iva/obligacion-presentar-declaraciones-informativas/modelo-347.html`

## Casilla Semantic Mapping (Core)

| Casilla | Label (ES) | Help (ES) |
| :--- | :--- | :--- |
| 01 | N.º total de personas y entidades | Número total de personas y entidades relacionadas en la declaración. |
| 02 | Importe total de las operaciones | Suma total de los importes de las operaciones declaradas. |

## Tasks
- [ ] Update `corpus/casillas/modelo_347/*.json`
- [ ] Update `corpus/casillas/modelo_349/*.json`
- [ ] Update `corpus/casillas/modelo_369/*.json`
