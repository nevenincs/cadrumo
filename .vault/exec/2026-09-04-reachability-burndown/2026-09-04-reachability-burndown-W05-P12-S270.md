---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:4578cfe8060d14a15ab945c9eb1c8cdd129590eac361bed20f9b9e74f62b80ee'
step_id: 'S270'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the test-only IVA remote-state stored-evidence aggregate while preserving the live compensation-history, wallet capture, acquisition-manifest, and reconciliation owners; migrate or remove only aggregate-specific assertions, run focused IVA live-state gates, update cadence, and remeasure exact reachability.

## Scope

- `test-only IVA remote-state stored-evidence aggregate`
- `its projection DTOs/helpers`
- `exports`
- `and aggregate-only assertions`

## Changes

- `M` `src/cadrumo/application/live/iva_remote_state.py`
- `M` `src/cadrumo/application/live/remote_state_models.py`
- `M` `src/cadrumo/application/live/tests/test_iva_wallet_capture_backend.py`
- `M` `src/cadrumo/application/live/tests/test_iva_remote_state_acquisition.py`
- `M` `src/cadrumo/application/live/tests/test_filed_capture_calculation_history.py`
- `M` `src/cadrumo/application/live/tests/test_live_iva_diagnostic_ref_shape.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync ruff check <focused IVA live-state files>` -> `pass`
- `verify:` `uv run --no-sync pytest -q -n0 src/cadrumo/application/live/tests/test_iva_wallet_capture_backend.py src/cadrumo/application/live/tests/test_iva_remote_state_acquisition.py src/cadrumo/application/live/tests/test_live_iva_diagnostic_ref_shape.py` -> `fail`
- `verify:` `uv run --no-sync pytest -q -n0 src/cadrumo/application/live/tests/test_filed_capture_calculation_history.py -k multiyear_303_submitted_file_parser_promotes_sanitized_iva_history` -> `pass`
- `verify:` `uv run --no-sync pytest -q -n0 src/cadrumo/application/live/tests/test_iva_wallet_capture_backend.py -k "iva_wallet_history_report_surfaces_lots_and_authority_decisions or remote_iva_evidence_roundtrips_through_profile_secure_sql"` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `fail`

## Notes

The initial focused run passed 32 tests and exposed one aggregate-specific test whose title claimed session bootstrap behavior the live storage span deliberately refuses; that test was removed with the facade. The two retained owner-level history/storage tests then passed. Exact unused symbols improved from 274 to 273; 31 unreachable modules and zero orphaned tests remain.
