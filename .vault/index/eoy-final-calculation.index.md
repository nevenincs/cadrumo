---
generated: true
tags:
  - '#index'
  - '#eoy-final-calculation'
date: '2026-08-16'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:f0cec4a04e30ae1452176e96c532f1826d0cfd258beb41246e18e39e3e16b3b8'
related:
  - '[[2026-06-21-eoy-final-calculation-audit]]'
  - '[[2026-06-22-eoy-final-calculation-adr]]'
  - '[[2026-06-22-eoy-final-calculation-plan]]'
  - '[[2026-06-30-eoy-final-calculation-research]]'
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
- `2026-06-22-eoy-final-calculation-P02-S04` - Confirm the M100 non-first-slice gastos advisory fires at parity with 2025 (no code unless missing)
- `2026-06-22-eoy-final-calculation-P02-S05` - Extend the 0004-domestic-base M303 ledger base aggregation to every supported 303 revision so base casilla 03/07/28 never populate cuota without base (F3)
- `2026-06-22-eoy-final-calculation-P02-S06` - Add M100 and M390 annual continuity regression coverage asserting the headline figure derives from period/ledger inputs, mirroring the M130 carry-forward tests

### plan

- `2026-06-22-eoy-final-calculation-plan` - `eoy-final-calculation` plan

### research

- `2026-06-30-eoy-final-calculation-research` - `eoy-final-calculation` research: `EOY final calculation current-state verification`
