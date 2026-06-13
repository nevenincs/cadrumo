---
tags:
  - '#exec'
  - '#corpus-data-hydration'
date: '2026-05-01'
modified: '2026-05-01'
related:
  - "[[2026-05-01-corpus-data-hydration-plan]]"
---

# `corpus-data-hydration` phase-4 task-4: Modelo 036, 037 (Censal)

Manual semantic extraction and hydration of Modelo 036 and 037 (Declaración Censal).

## Sourcing
Official AEAT documentation sourced:
- URL: `https://sede.agenciatributaria.gob.es/Sede/ayuda/manuales-videos-folletos/manuales-practicos/censos-nif-domicilio-fiscal/instrucciones-cumplimentacion-modelos-036-037.html`

## Casilla Semantic Mapping (Key identifiers used in the code)

| Casilla | Label (ES) | Help (ES) |
| :--- | :--- | :--- |
| causa_presentacion | Causa de presentación | Indique el motivo por el que presenta la declaración censal. |
| epigrafe_iae | Epígrafe IAE | Código del epígrafe del Impuesto sobre Actividades Económicas. |
| fecha_efectos | Fecha de efectos | Fecha en la que surten efectos las variaciones comunicadas. |
| regimen_irpf | Régimen de IRPF | Método de determinación del rendimiento neto (Estimación Directa o Objetiva). |
| regimen_iva | Régimen de IVA | Régimen aplicable en el IVA (General, Simplificado, etc.). |

## Tasks
- [ ] Update `corpus/casillas/modelo_036/*.json`
- [ ] Update `corpus/casillas/modelo_037/*.json`
