---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-27'
modified: '2026-08-27'
body_schema: 'body-v2'
body_hash: 'sha256:f9c85602edc414b1f1e2cf03d64b198db45f5d4eab479458f35d78d3dbdb8b6c'
step_id: 'S289'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Stop the modelo 184 socio record truncating a multi-member attribution to a single member: its export record carries twenty-seven manual scalar casilla fields, no binding fields and no repeat marker, while the per-row member bindings already exist in the registry and a real per-row resolver already computes their values, so every member beyond the first is computed correctly and never reaches the fichero; repoint the record's fields onto the existing per-row binding ids, declare the record repeating, and prove a real multi-member attribution emits one socio occurrence per member with the right values

## Scope

- `the modelo 184 socio export record declaration`
- `src/cadrumo/domain/calculations/registry/schema_exports.py if the repeat contract needs it`
- `and a real multi-member M184 export parity test`

## Changes

- `A` `src/cadrumo/application/modelo/tests/test_m184_multi_clave_export_parity.py::test_an_ordinary_multi_member_attribution_emits_one_row_per_member_with_the_right_values`
- `verify:` `pytest src/cadrumo/application/modelo/tests/test_m184_multi_clave_export_parity.py` -> `pass (12/12)`

## Notes

This Step's defect was already fixed as a byproduct of S299: the socio
export record in both revisions already declares `repeat = 'binding_rows'`
and `binding_record = 'miembro'`, and every money-bearing and identity
field is already `kind = 'binding'` (confirmed by grepping the live TOML —
only the five deliberately out-of-scope fields, representante-fiscal-nif,
tipo-hoja, clave-pais, clave-tipo-participe and provisiones-gastos, remain
`kind = 'casilla'`). No further repoint was needed; `schema_exports.py`'s
existing `binding_rows` contract already supported this shape (the same
mechanism M349's operador record already used), so no change there either.

The only genuine gap was proof scoped to PLAIN multi-member attribution
(this Step's own framing) rather than the multi-clave axis S299's own test
file already covered. Added
`test_an_ordinary_multi_member_attribution_emits_one_row_per_member_with_the_right_values`:
four distinct members, same clave, no clave variation -- proves each
resolves its own row index (no collision), that each row's `base_imponible_assigned`
matches the RIGHT member (not a swapped or truncated value), and that the
render layer emits one occurrence per resolved index. Traced the full
pipeline by hand to confirm no truncation survives anywhere upstream of the
export record either: `_project_attribution_socio_facts` sorts and returns
every complete socio with no cap, and `resolve_atribucion_binding_row_values`
resolves every observation to its own row index.
