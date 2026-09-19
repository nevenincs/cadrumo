---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-25'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:0893f74d11d352d4bf8dbd10c123f8c401dd519ac32f08db176023d05b95f4e2'
related:
  - '[[2026-08-11-tui-architecture-adr]]'
  - '[[2026-08-11-tui-architecture-plan]]'
---
# `tui-architecture` audit: `S41/S44 Google export operation and export facade`

## Scope

Independently re-reviewed the atomic `W03.P08.S41` and `W03.P08.S44` cutover against the accepted `tui-architecture` ADR, the roll-up plan, both execution records, and the current source tree. The review covered:

- `src/cadrumo/application/export/_google_operation.py`
- `src/cadrumo/application/export/__init__.py`
- `src/cadrumo/application/export/tests/test_google_operation.py`
- `src/cadrumo/entrypoints/_operation_composition.py`
- `src/cadrumo/entrypoints/cli/_config/_google_sync_calc.py`
- `src/cadrumo/entrypoints/cli/_config/_manager_actions.py`
- `src/cadrumo/entrypoints/tests/test_operation_composition.py`

## Findings

No open critical, high, medium, or low findings remain.

`_google_operation.py` owns the strict credential-free request, active-profile and capability admission, exact registry snapshot and plan construction, normalized remote result, supervised phase/effect sequence, and result custody. It imports no adapter, persistence, or entrypoint implementation. The sole remote boundary is the injected `GoogleSheetsExportPort`; the total default factory deliberately refuses an uncomposed remote call.

`application.export` is the sole public cross-package facade for the operation contracts and builders. The production composition seam imports that facade, registers the one `export.google-sheets` definition, and binds the only concrete transport. The apply branch calls `export_modelo_to_sheets` with `SyncRunRecordRepository()` and the real `apply_export_plan` adapter; the preview branch uses the real preview adapter. Therefore every production apply retains the existing sync-run provenance writer rather than reimplementing it.

Both CLI consumers now share the narrow `execute_google_sheets_export` input adapter. The command and manager contain no local export-plan, preview, or apply orchestration, and the prior duplicated manager planner/apply path is absent. There is no compatibility alias, non-package re-export bridge, private export-operation import, fabricated snapshot or plan, cast, `SimpleNamespace`, fake, mock, or stub in the focused operation tests.

The executor truth is exact: dry-run emits preflight, plan, preview, then `NONE`; apply emits preflight, plan, apply, then `UNKNOWN` before the irreversible section and `UPDATED` only after the port returns; the safe normalized result is written to encrypted operand custody before settlement. Capabilities truthfully declare recorded durability, unsupported cancellation, no deadline, no interactions, idempotent submit, interrupt reconciliation, and only `NONE`, `UNKNOWN`, or `UPDATED` effects.

## Verification

- RAG discovery located one application owner, one public export facade, and one entrypoint transport/provenance handoff.
- Scoped Ruff and `ty` passed for all S41/S44 application, composition, CLI, and focused test surfaces.
- `uv run --no-sync pytest -q -n0 -m integration src/cadrumo/application/export/tests/test_google_operation.py` passed: 4 tests in 51.57s, including the real Model 130 registry-plan / uncomposed-port refusal proof.
- `uv run --no-sync pytest -q -n0 -m integration src/cadrumo/entrypoints/tests/test_operation_composition.py` passed: 7 tests.
- `uv run --no-sync pytest -q -n0 -m 'not external_tool and not os_keychain' src/cadrumo/entrypoints/cli/tests/test_config_google_sync_calc_period.py src/cadrumo/entrypoints/cli/tests/test_google_payloads.py` passed: 13 tests in 59.97s.
- Exact source census found the only command/manager export route is `execute_google_sheets_export`; the only production apply is the composition handoff to `export_modelo_to_sheets`.
- `git diff --check` passed for the reviewed current tree.

## Recommendation

Approve the atomic S41/S44 implementation and close both steps after the normal Vault plan checks. This audit replaces the earlier pre-S44 deferral statement: facade exposure and CLI migration are completed together here, with no shim retained.
