---
tags:
  - '#audit'
  - '#retenciones-perceptor-count'
date: '2026-06-30'
modified: '2026-06-30'
related:
  - "[[2026-06-24-retenciones-perceptor-count-plan]]"
---

# `retenciones-perceptor-count` audit: `RET-1 current-state verification`

## Scope

Current-state audit of the RET-1 perceptor-count edge after the June 25 not-fixed note and the remaining P03 steps in `2026-06-24-retenciones-perceptor-count-plan`. The check covered M180, M193, and the M190 distinction because the original P03 wording grouped M190 with distinct-NIF perceptor counts.

## Findings

### ret-1-current | low | M180 and M193 now use the dedicated retenciones aggregation source

M180 binds `modelo-180-115-perceptores-anual` to `source = "retenciones_aggregation"` in both the `2019-2022` and `2023-y-siguientes` revisions, with `fact = "perceptor_count_distinct"` targeting `decl.total-perceptores`. M193 binds `modelo-193-123-perceptores-anual` the same way. The monetary base and retenciones totals remain on relation-prefill bindings.

### m190-scope | low | M190 is a withholding percepciones count, not a retenciones perceptor count

M190 correctly does not use `retenciones_aggregation` for `decl.total-percepciones`. The binding `modelo-190-percepciones-anual` uses `source = "withholding"` with `fact = "percepcion_count"` and counts distinct `(perceptor, clave, subclave)` rows. The P03.S08 wording was edited to document this as a scoped deviation from the obsolete grouping.

### m190-fixture-drift | medium | M190 reconciliation tests still seeded M111 bound casillas manually

The M190 verification command exposed a stale helper in `test_modelo_190_111_reconciliation_continuity.py`: `_calculate_111` called `resolve_bound_inputs_by_casilla_id` with empty binding facts after the M111 registry moved 01/02/03 onto `retenciones_aggregation`. The helper now creates typed `RetencionObservation` rows, aggregates them with `aggregate_retenciones_111`, resolves binding values with `resolve_retenciones_aggregation_binding_values`, and passes only remaining manual casillas as manual inputs.

### exec-record-drift | low | Checked retenciones steps lacked execution records

The plan had checked steps S01, S03, S04, and S05 without exec records. Retrospective current-state records were created with focused verification evidence so the plan can be audited without relying on memory or earlier chat context.

## Recommendations

- Keep P03.S07 through P03.S09 closed with the current verification evidence.
- Keep M190 on the withholding/percepciones surface; do not re-target it to `retenciones_aggregation`.
- Treat future retenciones fixture updates as bound-source setup, not manual input setup, whenever the registry casilla declares a binding.
