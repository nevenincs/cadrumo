---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:c5e5c7ed845fdc4aa35486dd119b28db18f6813f2bae82b90a9b12884f9f4f8e'
step_id: 'S285'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Refuse a detail row submitted against a modelo that cannot carry it, at the calculate boundary, for every row kind that lacks the check the M210 grouped-renta validator already performs: the M349 operador and rectificacion path currently returns an empty aggregation on a modelo mismatch so the rows persist into the revision while contributing nothing, and the M184 member, M232 vinculada and M347 contraparte kinds carry no membership check at all while their share-sum and threshold validations run unconditionally; make every kind refuse with an instructive error naming the row kind and the work unit's modelo, and prove a mismatched row of each kind is rejected rather than dropped or persisted

## Scope

- `src/cadrumo/application/modelo/_calculation_modelo_adjustments.py`
- `_calculate_input.py`
- `_revision_replay_inputs.py`
- `and focused per-row-kind modelo-membership refusal tests`

## Changes

- `M` `src/cadrumo/application/modelo/_calculation_modelo_adjustments.py`
- `M` `src/cadrumo/application/modelo/_calculation_actions.py`
- `A` `src/cadrumo/application/modelo/tests/test_detail_row_modelo_membership.py`
- `M` `src/cadrumo/locales/en/errors.yml`
- `M` `src/cadrumo/locales/es/errors.yml`
- `M` `src/cadrumo/locales/ca/errors.yml`
- `M` `src/cadrumo/locales/hu/errors.yml`
- `verify:` `uv run --no-sync pytest src/cadrumo/application/modelo/tests/test_detail_row_modelo_membership.py -q -n 0` -> `pass` (12 passed)
- `verify:` `uv run --no-sync pytest src/cadrumo/application/modelo/tests/test_modelo_210_agrupacion_renta_e2e.py src/cadrumo/application/modelo/tests/test_m349_calculation_display_export.py -q -n 0` -> `pass` (19 passed, confirms the new guard admits every already-correct modelo/row combination)
- `verify:` `uv run --no-sync ty check src/cadrumo/application/modelo/_calculation_actions.py src/cadrumo/application/modelo/_calculation_modelo_adjustments.py src/cadrumo/application/modelo/tests/test_detail_row_modelo_membership.py` -> `pass` (1 pre-existing unrelated unsound-assignment diagnostic confirmed present before this change)
- `verify:` `uv run --no-sync ruff check src/cadrumo/application/modelo/_calculation_actions.py src/cadrumo/application/modelo/_calculation_modelo_adjustments.py src/cadrumo/application/modelo/tests/test_detail_row_modelo_membership.py` -> `pass`

## Notes

One shared function, `require_detail_rows_declared_for_their_owning_modelo`,
covers all five kinds through one refusal convention (`ModeloError`, a new
`errors.error.error_modelo_detail_row_wrong_modelo` locale key naming the row
type, its owning modelo, and the work unit's actual modelo), called once at
the calculate boundary's single funnel
(`_calculate_modelo_revision_with_trusted_mesh_sources`) so both the direct
and bucket-aggregation calculate entry points are covered without
duplicating the check per path.

Checked whether anything relies on M349's prior silent-drop behavior
(`_detail_row_binding_values_for_calculation` returning `{}` on a modelo
mismatch): no test or caller submits an M349 row against a non-M349 work
unit expecting silent success; the new upstream refusal makes that branch
unreachable for a mismatched row while leaving its "no M349 rows, non-M349
modelo" short-circuit (still legitimately needed) untouched. No change was
needed in that function.

`_calculate_input.py` and `_revision_replay_inputs.py`, named in the Step's
own scope, were not touched: `_calculate_input.py`'s `_validate_detail_rows`
is a CLI-side pre-check that runs before the calculate boundary either path
reaches, and the new guard already covers both paths downstream regardless
of which one a caller uses; `_revision_replay_inputs.py` only reads an
already-persisted revision back and cannot itself prevent a bad write.
Duplicating the check in either would risk the two diverging later.

Locale scaffold also touched `en/cli.yml`, `es/cli.yml`, `ca/cli.yml`,
`hu/cli.yml`, and each locale's `modelo/schema/181.yml` with unrelated
pre-existing drift from concurrent work in this shared worktree; those were
reverted (`git checkout --`) before committing, leaving only the new key.
