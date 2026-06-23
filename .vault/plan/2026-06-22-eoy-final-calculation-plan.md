---
tags:
  - '#plan'
  - '#eoy-final-calculation'
date: '2026-06-22'
modified: '2026-06-23'
tier: L2
related:
  - '[[2026-06-22-eoy-final-calculation-adr]]'
  - '[[2026-06-21-eoy-final-calculation-audit]]'
---


# `eoy-final-calculation` plan

### Phase `P01` - Fix M200 cuota liquida derivation (F2)

Convert casilla DP200014B:00592 (cuota liquida) from a bare manual input into a computed casilla derived from cuota integra so the IS annual result stops silently reading zero.

- [x] `P01.S01` - Ground the LIS deduccion/bonificacion casilla set that reduces cuota integra (00562) to cuota liquida (00592) against the AEAT Modelo 200 Diseno de Registros / Manual practico; `src/aeat/_data/registry/aeat/modelos/200`.
- [ ] `P01.S02` - Convert casilla DP200014B:00592 to a computed casilla deriving cuota liquida from 00562 minus the grounded deduction/bonificacion casillas (each defaulting to 0); `wire the owning construct and legal_refs (coordinate with the task-5 M200 owner; re-read HEAD before editing); `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes`.
- [ ] `P01.S03` - Add real end-to-end regression asserting M200 cuota del ejercicio a ingresar (00599) derives from cuota integra minus pagos (no manual 00592), grounded not tautological; `src/aeat/application/modelo/tests`.

### Phase `P02` - Confirm F1 residual, extend M303 base (F3), annual regression coverage

Close the adjacent end-of-year aggregation gaps and lock the headline-figure derivation with real end-to-end regression tests.

- [ ] `P02.S04` - Confirm the M100 non-first-slice gastos advisory fires at parity with 2025 (no code unless missing); `src/aeat/_data/registry/aeat/modelos/100`.
- [ ] `P02.S05` - Extend the 0004-domestic-base M303 ledger base aggregation to every supported 303 revision so base casilla 03/07/28 never populate cuota without base (F3); `src/aeat/_data/registry/aeat/modelos/303`.
- [ ] `P02.S06` - Add M100 and M390 annual continuity regression coverage asserting the headline figure derives from period/ledger inputs, mirroring the M130 carry-forward tests; `src/aeat/application/modelo/tests`.

## Description

This plan closes the end-of-year annual final-calculation gaps surfaced by the 2026-06-21 EOY audit
and decided in the accepted ADR. F1 (M100 annual business income) already landed during the campaign;
the open work is F2 (M200 cuota liquida derivation), the adjacent F3 (M303 base aggregation across all
303 revisions), and locking annual headline-figure derivation behind real regression tests. The
authorising ADR and audit are listed in `related:`. Phase blocks appear above; this section is prose.

## Steps







## Parallelization

P01 and P02 are independent and may run in parallel. Within P01: S01 (grounding) precedes S02 (the
formula change) precedes S03 (regression). P01.S02 edits the M200 2024 registry, which is actively
worked under tasks #5 / #13 - sequence against that owner and re-read HEAD plus `git diff` the touched
200 registry files immediately before editing. P02.S04 (M100 confirm), S05 (M303 base), and S06
(regression) carry no hard interdependency.

## Verification

Complete when every Step is closed. Success criteria: a Modelo 200 with a positive cuota integra and
no manually-entered cuota liquida produces a non-zero cuota del ejercicio a ingresar (00599) derived
from 00562 minus the grounded deduction/bonificacion casillas; the M200 end-to-end regression (S03)
and the M100/M390 annual continuity tests (S06) pass; M303 base casillas 03/07/28 populate alongside
their cuotas on every supported revision (S05); the full registry builds and feature-scoped
`vaultspec-core vault check` is clean.
