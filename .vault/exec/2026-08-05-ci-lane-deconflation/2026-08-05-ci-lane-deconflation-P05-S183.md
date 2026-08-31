---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:0824fe810ff7f50fa2233773317315c949150932eb43eacfa05234c3ab0d4d26'
step_id: 'S183'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
# Refactor the size-budget subjects in bindings.py into cohesive siblings without raising any threshold.

## Scope

- `src/cadrumo/domain/calculations/registry/bindings.py`

## Changes

- `M` `src/cadrumo/application/calculations/_m303_regimen_simplificado_annual_summary.py`
- `M` `src/cadrumo/application/modelo/_calculation_modelo_adjustments.py`
- `M` `src/cadrumo/application/modelo/_data_inventory.py`
- `M` `src/cadrumo/application/modelo/_revision_replay_inputs.py`
- `M` `src/cadrumo/application/modelo/tests/test_modelo_390_303_simplificado_fold_in_live.py`
- `M` `src/cadrumo/application/modelo/work_review.py`
- `M` `src/cadrumo/application/registry/source_connectivity.py`
- `M` `src/cadrumo/domain/calculations/registry/_validate_record_sections.py`
- `A` `src/cadrumo/domain/calculations/registry/binding_targets.py`
- `M` `src/cadrumo/domain/calculations/registry/bindings.py`
- `M` `src/cadrumo/domain/calculations/registry/formula_initial_values.py`
- `M` `src/cadrumo/domain/calculations/registry/handoffs.py`
- `A` `src/cadrumo/domain/calculations/registry/m303_regimen_simplificado_annual_summary_bindings.py`
- `M` `src/cadrumo/domain/calculations/registry/rate_box_partition.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_casillas_by_binding.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_inventory_casilla_binding_linkage.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_m390_m303_regimen_simplificado_annual_summary_bindings.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_relation_handoff_inventory.py`
- `A` `.vault/exec/2026-08-05-ci-lane-deconflation/2026-08-05-ci-lane-deconflation-P05-S183.md`
## Notes

- The public `bindings.py` surface was reduced below the unchanged 1,250-line module policy by moving cohesive binding-family logic to defining sibling modules. The independent source review observed a live 894-line primary; the prior executor observed 1,032 lines during the same shared-tree work. Both are below policy, and every extracted helper is at most 179 lines under the unchanged 180-line callable policy. No baseline or threshold change belongs to this Step.
- The supplied focused receipt is executor-reported only: `48 passed in 51.93s`. Its literal command was not retained, so this record deliberately does not invent a `verify:` command.
- Independently reviewed targeted Ruff/check, import, and compile probes were clean. The non-mutating full size audit stalled and yielded no result; this record makes no global size-audit pass claim.
- `src/cadrumo/application/modelo/_calculation_actions.py` carries concurrent relocation work. The source commit stages the reviewed bindings extraction with an isolated index and excludes that peer relocation.

