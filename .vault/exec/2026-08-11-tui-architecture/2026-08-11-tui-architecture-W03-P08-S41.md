---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:c3a8471efa67fb7fb14348b7d843318182136d4dea464a55f7880d8284dc2555'
step_id: 'S41'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
# Move Google export planning and application orchestration out of the CLI frontend and register its external-effect operation

## Scope

- `src/cadrumo/application/export/_google_operation.py`
- `src/cadrumo/application/export/tests/test_google_operation.py`
- `src/cadrumo/entrypoints/_operation_composition.py`
- `src/cadrumo/entrypoints/cli/_config/_google_sync_calc.py`
- `src/cadrumo/entrypoints/cli/_config/_manager_actions.py`
- `src/cadrumo/entrypoints/tests/test_operation_composition.py`

## Description

- Centralize active-profile admission, Google egress capability evaluation, registry snapshot selection, workbook plan construction, remote handoff, and safe result normalization in `GoogleSheetsExportService`.
- Keep the registered executor responsible for phases, irreversible apply truth, effect settlement, and encrypted operand custody while sharing the service path with synchronous CLI consumers.
- Compose the sole concrete Google transport at the entrypoint boundary; require every apply to call `export_modelo_to_sheets` with `SyncRunRecordRepository` and the real `apply_export_plan` adapter.
- Delete the duplicated manager export planner and the CLI command's local plan/preview/apply orchestration; both now adapt input once and consume the public application contract.
- Replace fabricated snapshots, plans, casts, and transport fakes with real registry-plan, real supervision, production-composition, and exact provenance-handoff evidence.

## Outcome

S41 now has one application owner and one outer Google/provenance composition. The operation owner has no adapter, persistence, or entrypoint imports; the production registry binds its injected transport. CLI and manager consumers no longer reimplement export planning or bypass sync-run provenance.

## Verification

- Scoped Ruff and `ty` checks pass for all changed application, composition, and CLI surfaces.
- The explicit 60-second real model-130 registry-plan gate passes and refuses the intentionally uncomposed remote boundary without a fabricated port.
- The remaining focused export tests, production-composition fixed-point tests, and CLI schema/payload tests pass: 24 passed in the non-slow lane.
- Exact census finds no `SimpleNamespace`, `cast`, manager duplicate, or CLI plan/preview/apply call; the sole production apply calls `export_modelo_to_sheets`.
- `git diff --check` passes.

## Notes

S41 remains open pending independent S40 re-review. No compatibility shim, private application import, or facade re-export bridge was introduced.
