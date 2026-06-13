---
tags:
  - '#exec'
  - '#corpus-data-hydration'
date: '2026-05-01'
modified: '2026-05-01'
related:
  - "[[2026-05-01-corpus-data-hydration-plan]]"
---

# `corpus-data-hydration` phase-3 task-4: Modelo 180, 190, 193 (Summaries)

Manual semantic extraction and hydration of Modelo 180, 190, and 193 (Annual withholding summaries).

## Sourcing
Official AEAT documentation sourced:
- Modelo 190: `https://sede.agenciatributaria.gob.es/Sede/ayuda/manuales-videos-folletos/manuales-practicos/irpf-2025/capitulo-18-gestion-impuesto/retenciones-ingresos-cuenta/declaraciones-informativas-resumenes-anuales.html`

## Casilla Semantic Mapping (Generic Summaries)

These models aggregate the quarterly data. The core casillas are:
- **Modelo 180** (Resumen 115): Total rental withholdings.
- **Modelo 190** (Resumen 111): Total labor/economic activity withholdings.
- **Modelo 193** (Resumen 123): Total movable capital withholdings.

## Tasks
- [ ] Update `corpus/casillas/modelo_180/*.json`
- [ ] Update `corpus/casillas/modelo_190/*.json`
- [ ] Update `corpus/casillas/modelo_193/*.json`
