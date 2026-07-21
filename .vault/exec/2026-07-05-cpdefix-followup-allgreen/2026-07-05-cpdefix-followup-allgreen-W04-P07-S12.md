---
tags:
  - '#exec'
  - '#cpdefix-followup-allgreen'
date: '2026-07-05'
modified: '2026-07-17'
step_id: 'S12'
related:
  - "[[2026-07-05-cpdefix-followup-allgreen-plan]]"
---

# Revalidate current M130 gasto actividad-economica eligibility against production aggregation

## Scope

- `src/aeat/application/aggregation/_renta_gasto_ledger.py`

## Description

- Revalidated the persona EDGE-HIGH-2 M130 gasto asymmetry against current production code with `uvx vaultspec-rag search`.
- Confirmed `src/aeat/application/aggregation/_renta_income_ledger.py` already treats `irpf_category=actividad_economica` as the M130 income eligibility gate.
- Confirmed `src/aeat/application/aggregation/_renta_gasto_ledger.py` still used only `business_classification` and `business_pct`, so an outgoing activity expense tagged by IRPF category but still `NOT_YET_PROCESSED` was dropped.
- Checked current official grounding: AEAT Modelo 130 instructions place casilla 01 and casilla 02 in the same accumulated direct-estimation activity section; BOE RD 439/2007 art. 110 calculates the payment from direct-estimation net yield over the same year-to-date period.

## Outcome

- The post-completion edge was live in the current tree, not stale.
- `W04` was added to the existing `cpdefix-followup-allgreen` plan so the reopened edge is tracked as current work rather than hidden under the completed plan state.

## Notes

- The shared worktree was already dirty with unrelated peer work. This step touched only the cpdefix plan and the M130 gasto aggregation surface.
