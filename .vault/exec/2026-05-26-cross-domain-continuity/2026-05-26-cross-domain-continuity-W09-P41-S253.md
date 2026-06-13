---
tags:
  - "#exec"
  - "#cross-domain-continuity"
step_id: S253
date: 2026-05-27
modified: '2026-05-27'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-05-26-cross-domain-continuity-W09-P41-S252]]"
  - "[[2026-05-26-cross-domain-continuity-W09-P41-S208]]"
---

# cross-domain-continuity W09.P41.S253 — Category B batch 2 storage migration

## Outcome

Migrated 5 of 12 Category B test files to the secure fixture pattern. The
remaining 6 files carry foreign WIP and were left untouched per batch contract.
One file (`test_modelo_source_mesh_calculate.py`) was already migrated before
this step. A pre-existing production bug in `ledger_transaction_payload` was
uncovered and fixed.

### Files migrated

| File | Fixture used | Result |
|------|-------------|--------|
| `test_apex_workflow_verification.py` | `isolated_profile_storage_root` | 17/18 PASS |
| `test_cli_surface.py` | `isolated_profile_storage_root` | 21/21 PASS |
| `test_profile_output_language.py` | `isolated_profile_storage_root` | 6/6 PASS |
| `test_session_lifecycle_roundtrip.py` | `EphemeralMasterKeyProvider` (no change needed) | 5/5 PASS |
| `test_modelo_source_mesh_calculate.py` | `isolated_runtime_profile` (pre-migrated) | pass |

### Foreign-WIP files — untouched

`test_audit_remediation`, `test_command_suggestions`, `test_modelo_discovery_defects`,
`test_modelo_period_consistency`, `test_modelo_work_applicability_guard`, `test_modelo_work_ux`

### Not applicable

`test_modelo_202_modality` — pure domain test, no storage fixture needed.

## Production bug fixed

`src/aeat/application/ledger/_actions.py` — `ledger_transaction_payload` passed
`counterparty=raw.counterparty` (which is `None` for manual ledger rows) to
`LedgerTransactionPayload`. The model uses strict pydantic config; `None` fails
validation for the `str` field even with a `= ""` default. Fixed with
`counterparty=raw.counterparty or ""`. This regression was masked by the old
unsecured-backend test setup and surfaced only when `test_cli_surface.py` moved
to the real encrypted backend.

## Key insight: per-bucket vs fallback database in isolated_profile_storage_root

`isolated_profile_storage_root` freezes `aeat_database_url` to the fallback
`<storage_root>/aeat.db` at construction time (no pointer file exists yet).
`profile_create_storage_span` opens an inner `override_settings(aeat_active_profile=
profile_id)`, so `profile create` writes all state (including `bucket_events`) to
the per-bucket database, not the fallback. Tests that assert `bucket_events` after
a CLI `profile create` must wrap the state-read in
`override_settings(aeat_active_profile=bucket_id)` to redirect `aeat_database_url`
to the per-bucket database.

## Pre-existing blocker in test_apex_workflow_verification

`test_config_app_round_trip_certificate_auth_status_reports_configured` fails with
the auth `configure` and `status` verbs producing contradictory JSON payloads. This
is a pre-existing issue unrelated to the storage migration; it was already failing
before this batch.

## Commits

- `cf7775ebe` — Task #82: storage migration S253 Batch 2 — secure fixture for 5 CLI test files

## Files changed

- `src/aeat/application/ledger/_actions.py` — counterparty coercion fix
- `src/aeat/entrypoints/cli/test_apex_workflow_verification.py`
- `src/aeat/entrypoints/cli/test_cli_surface.py`
- `src/aeat/entrypoints/cli/test_profile_output_language.py`
- `src/aeat/entrypoints/cli/test_session_lifecycle_roundtrip.py`
