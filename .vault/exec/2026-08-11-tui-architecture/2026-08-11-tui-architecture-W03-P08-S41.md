---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:f3487bf6eae21d8ddd0fbd31b1b4c11136d398b22c40a94b44ef2beb8c970fad'
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
- Real contract, production composition, and AST provenance tests pass; the real default-owner registry-plan proof is running separately because model `130` plan construction is CPU-bound.
- CLI command-schema and payload tests pass.
- `git diff --check` passes.

## Notes

S41 remains open pending the focused real-plan gate, Vault check, and independent S40 re-review. No compatibility shim, private application import, or facade re-export bridge was introduced.
