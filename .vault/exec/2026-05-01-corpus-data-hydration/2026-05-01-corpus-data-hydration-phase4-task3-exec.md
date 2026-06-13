---
tags:
  - '#exec'
  - '#corpus-data-hydration'
date: '2026-05-01'
modified: '2026-05-01'
related:
  - "[[2026-05-01-corpus-data-hydration-plan]]"
---

# `corpus-data-hydration` phase-4 task-3: Modelo 232, 720, 840 (Misc)

Manual semantic extraction and hydration of Modelo 232, 720, and 840.

## Sourcing
Official AEAT documentation sourced:
- Modelo 720: `https://sede.agenciatributaria.gob.es/Sede/ayuda/manuales-videos-folletos/manuales-practicos/modelo-720.html`

## Casilla Semantic Mapping (Core)

| Modelo | Casilla | Label (ES) | Help (ES) |
| :--- | :--- | :--- | :--- |
| 232 | num_registros_vinculadas | N.º registros operac. vinculadas | Número total de registros de operaciones con personas o entidades vinculadas. |
| 720 | num_registros_cuentas | N.º registros de cuentas | Número total de cuentas en entidades financieras situadas en el extranjero. |
| 840 | 14 | Epígrafe IAE | Código del epígrafe de la actividad en el Impuesto sobre Actividades Económicas. |

## Tasks
- [ ] Update `corpus/casillas/modelo_232/*.json`
- [ ] Update `corpus/casillas/modelo_720/*.json`
- [ ] Update `corpus/casillas/modelo_840/*.json`
