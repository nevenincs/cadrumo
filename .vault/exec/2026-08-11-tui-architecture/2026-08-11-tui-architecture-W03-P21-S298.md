---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:b6422c4929bc7dd3b998e4a08aa579ae0e4dedfd69be18de32343bb3c27e5499'
step_id: 'S298'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Stop a modelo 349 declarant summary over-declaring when the same operation reaches it from two supply paths: resolver-produced and caller-supplied detail rows are concatenated with no identity comparison, so an invoice-sourced operador row that the operator also enters manually is counted twice, inflating both the declared operator count and the declared amount; union the two sources by each row kind's own natural identity, refuse with an instructive conflict naming the counterparty and the divergent fields when the two disagree, union cleanly when they agree, and prove the summary totals are unchanged for every modelo whose rows come from one source alone

## Scope

- `src/cadrumo/application/modelo/_calculation_actions.py detail-row composition`
- `_calculation_modelo_adjustments.py summary derivation`
- `and focused two-source collision`
- `clean-union and divergence-refusal tests for modelo 349`

## Changes

- `M` `src/cadrumo/application/modelo/_calculation_actions.py`
- `M` `src/cadrumo/application/modelo/_calculation_modelo_adjustments.py`
- `M` `src/cadrumo/application/modelo/tests/test_calculation_modelo_adjustments.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/application/modelo/tests -q -m unit -k "m349 or detail_row or calculation_actions or calculation_modelo_adjustments"` -> `pass` (36 passed)
- `verify:` `uv run --no-sync pytest --collect-only -q src/cadrumo/application/modelo` -> `pass` (1980/2258 collected, 278 deselected, unchanged)

## Notes

Confirmed the defect live before fixing it, with the real production
function rather than an approximation: `detail_row_binding_values_for_
calculation` given a resolver-produced M349 operador row plus a manual
duplicate for the same `(nif_comunitario, clave_operacion)` returned
`numero_operadores=2, importe_operaciones=2000.00` for one real
operation of 1000.00 entered once through each supply path. Confirmed
separately that the Tipo-2 operador export rows do NOT duplicate --
manual detail rows never produce row-indexed `(BindingId, row_index)`
values, only the four scalar declarant-summary bindings -- so this was
a wrong summary total, not a doubled fichero row.

`union_detail_rows_by_identity` groups by `(row_type, natural identity)`
using a per-row-kind field-tuple table (`_ROW_IDENTITY_FIELDS`): nif for
M184, (nif, tipo_operacion) for M232, (nif, clave_operacion) for M347,
(nif_comunitario, clave_operacion) for M349 operador,
(nif_comunitario, clave_operacion, ejercicio, periodo) for M349
rectificacion, source_id for M210. A group fed by one supply path passes
through; a group both paths name unions to the resolver's row when every
other field agrees; a divergent group raises `ModeloAggregationBindingError`
(reason `detail_row_identity_conflict`) naming the identity and the
sorted divergent field names.

Verified `_raise_if_m349_intracom_ledger_rows_need_operator_rows` cannot
newly refuse post-fix: it reads row PRESENCE only, and the union never
reduces a non-empty identity group to zero rows, so collapsing a
duplicate cannot flip presence to absence.

Follow-through gap closed: `uncovered_detail_row_kinds()` derives required
coverage from `ModeloDetailRow`'s own union members (`typing.get_args`),
not a hand-listed set, so a new row kind added without a matching
`_ROW_IDENTITY_FIELDS` entry reds the gate instead of silently
regressing this fix -- the identity-unique fallback is safe (never
wrongly merges) but was previously silent about never unioning a
genuine duplicate for an uncovered kind. Proved the gate bites:
`_uncovered_row_kinds` with one real kind removed from a copy of the
table detects exactly that kind; the real table is untouched. Commit
`5392365db2`.
