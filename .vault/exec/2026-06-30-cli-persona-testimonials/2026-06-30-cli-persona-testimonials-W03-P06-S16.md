---
tags:
  - '#exec'
  - '#cli-persona-testimonials'
date: '2026-06-30'
modified: '2026-06-30'
step_id: 'S16'
related:
  - "[[2026-06-30-cli-persona-testimonials-plan]]"
---

# Replay mixed-income autonomo and employee persona roots

## Scope

- `tmp/personas`

## Description

- Replayed the mixed-income employee plus autonomo testimony against current
  Modelo 100 and Modelo 130 calculation paths.
- Checked whether actividad-economica ledger income still drops from M100 or is
  now bound into casilla `0171`.
- Kept M100 export artifact absence separate from calculation correctness.

## Outcome

No current M100/M130 calculation defect reproduced. Current M100 2024 registry
binds casilla `0171` to `ledger_renta_income_aggregation`, and the replay
combined M130 autonomo income with manual salary inputs in the annual M100
projection. M100 local export refusal is explicit unsupported-surface behavior,
not a silent calculation failure.

## Notes

Verification evidence included the required RAG search, 3 focused M100/M130
registry and retenciones tests, 1 explicit M100 export-refusal test, and a real
CLI projection replay with base increasing from `48000.00` to `78000.00` after
adding salary casilla `0003=30000`.
