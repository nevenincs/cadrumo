---
generated: true
tags:
  - '#index'
  - '#eoy-final-calculation'
date: '2026-06-24'
modified: '2026-06-24'
related:
  - '[[2026-06-21-eoy-final-calculation-audit]]'
  - '[[2026-06-22-eoy-final-calculation-P01-S01]]'
  - '[[2026-06-22-eoy-final-calculation-P01-S02]]'
  - '[[2026-06-22-eoy-final-calculation-P01-S03]]'
  - '[[2026-06-22-eoy-final-calculation-adr]]'
  - '[[2026-06-22-eoy-final-calculation-plan]]'
---

# `eoy-final-calculation` feature index

Auto-generated index of all documents tagged with `#eoy-final-calculation`.

## Documents

### adr

- `2026-06-22-eoy-final-calculation-adr` - `eoy-final-calculation` adr: `Annual returns must derive their headline figures (M100 income, M200 cuota liquida)` | (**status:** `accepted`)

### audit

- `2026-06-21-eoy-final-calculation-audit` - `eoy-final-calculation` audit: `End-of-year annual final-calculation aggregation gaps (M100 income, M200 cuota)`

### exec

- `2026-06-22-eoy-final-calculation-P01-S01` - Ground the LIS deduccion/bonificacion casilla set that reduces cuota integra (00562) to cuota liquida (00592) against the AEAT Modelo 200 Diseno de Registros / Manual practico
- `2026-06-22-eoy-final-calculation-P01-S02` - Convert casilla DP200014B:00592 to a computed casilla deriving cuota liquida from 00562 minus the grounded deduction/bonificacion casillas (each defaulting to 0)
- `2026-06-22-eoy-final-calculation-P01-S03` - Add real end-to-end regression asserting M200 cuota del ejercicio a ingresar (00599) derives from cuota integra minus pagos (no manual 00592), grounded not tautological

### plan

- `2026-06-22-eoy-final-calculation-plan` - `eoy-final-calculation` plan
