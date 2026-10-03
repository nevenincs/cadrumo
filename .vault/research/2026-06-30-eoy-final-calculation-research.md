---
tags:
  - '#research'
  - '#eoy-final-calculation'
date: '2026-06-30'
modified: '2026-10-03'
body_hash: 'sha256:6bec1490db0639012d8cad04556a5895d740f4adf320349fdab58a0ee429cda0'
related:
  - "[[2026-06-22-eoy-final-calculation-adr]]"
  - "[[2026-06-22-eoy-final-calculation-plan]]"
---

# `eoy-final-calculation` research: `EOY final calculation current-state verification`

This research records the 2026-06-30 current-state verification for the
remaining `eoy-final-calculation` P02 steps. The aim was to separate stale plan
items from live calculation defects before closing the plan.

## Findings

- RAG grounding for the M202/M200 edge found that the old audit sentence was
  about M200 cuota-liquida propagation, not a remaining M202 pagos-fraccionados
  fold defect. Current tests cover both M202 modalidades: casilla `03` for LIS
  art. 40.2 and casilla `34` for LIS art. 40.3.
- RAG grounding for the M303 base edge found current registry/test coverage for
  both supported Modelo 303 revisions: `2009-y-siguientes` and
  `2023-y-siguientes`. Both now carry domestic base aggregation so ledger-driven
  base boxes no longer stay zero while cuota boxes populate.
- A runtime registry probe loaded M100/2024 and M100/2025 snapshots. Both bind
  first-slice expense casillas `0186`, `0192`, `0199`, and `0203` to
  `ledger_renta_expense_aggregation` with `fact = "deductible_amount_sum"` over
  annual period `0A`. The first-slice routing table is still closed to those
  four targets, so non-first-slice expenses remain advisory/manual by design.
- Focused M303/M200 verification passed:
Historical command omitted; its target file was removed.
  reported 13 passed.
- Focused M100/M390 annual verification passed:
Historical command omitted; its target file was removed.
  reported 21 passed.
