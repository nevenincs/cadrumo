---
tags:
  - '#exec'
  - '#cpdefix-followup-allgreen'
date: '2026-07-05'
modified: '2026-07-17'
step_id: 'S09'
related:
  - "[[2026-07-05-cpdefix-followup-allgreen-plan]]"
---

# Run scoped calculation application and registry test gates before making any allgreen claim

## Scope

- `src/aeat/application/`

## Description

- Tried the broad application aggregation, application modelo, and registry directory gate first.
- Split the gate after the broad command exceeded the timeout without useful pytest output.
- Ran the application aggregation directory gate.
- Ran a selected application modelo calculation/source/binding/fold-in gate.
- Fixed one live stale internal test call after RAG and exact grep proved production already passes `foreign_asset_observations` into `_resolve_bucket_source_mesh`.
- Ran a bounded calculation registry gate covering binding aggregation, detail records, M184, M347, M720, informativas, source enrollment, and support matrix.

## Outcome

The scoped split gates are green at current HEAD.

Initial broad attempt:

`uv run --no-sync pytest -q -n 0 src/aeat/application/aggregation/tests src/aeat/application/modelo/tests src/aeat/domain/calculations/registry/tests --tb=short`

Result: timed out after 604044 ms. Orphaned pytest processes from that exact command were stopped; unrelated vaultspec MCP and another worker's single-file registry pytest were left alone.

Application aggregation gate:

`uv run --no-sync pytest -q -n 0 src/aeat/application/aggregation/tests --tb=short`

Result: 430 passed, 4 deselected in 29.32s.

Application modelo calculation/source selected gate initially failed on `test_source_mesh_excludes_303_iva_compensation_relation_binding` because a direct test helper call omitted the now-required `foreign_asset_observations` keyword. RAG and exact grep showed production has one `_resolve_bucket_source_mesh` call and already passes the keyword. The fix added explicit `foreign_asset_observations=()` at the stale direct test call.

Rerun:

`uv run --no-sync pytest -q -n 0 src/aeat/application/modelo/tests -k "calculation or source or binding or fold_in_live or e2e or dormant or bucket_aggregation or revision_replay or prior_payment or prorrata or bienes_inversion or m347 or m349 or m720" --tb=short`

Result: 277 passed, 775 deselected in 230.67s.

Bounded calculation registry gate:

`uv run --no-sync pytest -q -n 0 src/aeat/domain/calculations/registry/tests/test_binding_aggregation.py src/aeat/domain/calculations/registry/tests/test_binding_build_validation.py src/aeat/domain/calculations/registry/tests/test_binding_source_kind_taxonomy.py src/aeat/domain/calculations/registry/tests/test_counterpart_bindings.py src/aeat/domain/calculations/registry/tests/test_detail_record_observations.py src/aeat/domain/calculations/registry/tests/test_detail_record_row_builders.py src/aeat/domain/calculations/registry/tests/test_invoice_bindings.py src/aeat/domain/calculations/registry/tests/test_modelo_184_registry.py src/aeat/domain/calculations/registry/tests/test_modelo_347_registry.py src/aeat/domain/calculations/registry/tests/test_modelo_347_registry_bindings.py src/aeat/domain/calculations/registry/tests/test_modelo_720_registry.py src/aeat/domain/calculations/registry/tests/test_modelo_informativas_batch2_registry.py src/aeat/domain/calculations/registry/tests/test_modelo_informativas_batch3_registry.py src/aeat/domain/calculations/registry/tests/test_source_enrollment.py src/aeat/domain/calculations/registry/tests/test_support_matrix.py --tb=short`

Result: 174 passed in 38.07s.

No allgreen claim is made for the full tree or for the timed-out monolithic command.

## Notes

- Product call paths did not require code changes for the `foreign_asset_observations` keyword.
- The only code edit under this step is the explicit empty tuple at the stale direct test helper call.
