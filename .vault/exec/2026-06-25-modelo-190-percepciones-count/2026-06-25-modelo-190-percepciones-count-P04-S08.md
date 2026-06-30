---
tags:
  - '#exec'
  - '#modelo-190-percepciones-count'
date: '2026-06-30'
modified: '2026-06-30'
step_id: 'S08'
related:
  - "[[2026-06-25-modelo-190-percepciones-count-plan]]"
---

# Retire the nine op=sum percepciones relations and drop their dependency entries

## Scope

- `src/aeat/_data/registry/aeat/modelos/190/revisions/2024-y-siguientes`

## Description

- Inspect current M190 relation, formula, construct, and dependency-classification records.
- Run M190/111 reconciliation continuity coverage.

## Outcome

- The retired quarterly perceptor-count relations are absent from the current M190 relation set.
- The M190 registry retains the nine monetary M111 importe relations and the one M111 retenciones relation, so `decl.percepciones-total` and `decl.retenciones-total` stay additive relation folds.
- `test_modelo_190_111_reconciliation_continuity.py` documents that the retired quarterly count relations remain absent and proves `decl.total-percepciones` derives from distinct withholding percepciones instead.
- Verification passed in the combined M190 slice: 22 passed.

## Notes

- No registry edit was needed for S08.
