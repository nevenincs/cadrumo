---
tags:
  - '#exec'
  - '#live-censo-calendar-reconciliation'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S15'
related:
  - '[[2026-06-05-live-censo-calendar-reconciliation-plan]]'
---

# W05.P05.S15 - typed Period boundary verification

## Description

- Verify the registry CLI and filed-state paths consume typed `core.Period` values while passing registry-token strings to registry revision selection.
- Verify IVA wallet and live filed-data text rows stringify typed periods at the CLI boundary.
- Verify overview calendar evidence uses typed periods for local filing records, AEAT filed observations, persisted justificantes, and profile-scoped evidence merges.
- Re-run pull-only command conformance to keep `pull-all` drift closed after the period stringification changes.

## Outcome

The focused gate now covers the typed-period drift that landed after S14. Registry deadline reports serialize deadline-window periods through canonical registry tokens, filed-state verification converts captured typed periods back to registry tokens for revision selection, and live/overview tests construct typed periods at strict model boundaries.

The code review found that an IVA wallet history payload still stringified typed `Period`, live filed text rows emitted display periods instead of registry tokens, and pull-only help keys still used stale `capture_all` names. Those findings are resolved: JSON payloads preserve typed `Period` at strict application boundaries, operator text uses registry tokens such as `1T`, and live filed/expedientes help keys are now `pull_modelo_help`.

The calendar contract remains separated into local filing readiness and observed AEAT submission/justificante verification. Imported justificante/live-backed filing records still require bound justificante metadata before being treated as verified evidence, and pull-only live CLI command conformance remains green.

## Notes

Verification passed:

- `uv run ruff check src/aeat/entrypoints/cli/_app_live.py src/aeat/entrypoints/cli/_app_live_expedientes_cli.py src/aeat/entrypoints/cli/tests/test_registry_cli.py` passed.
- `uv run pytest src/aeat/entrypoints/cli/tests/test_registry_cli.py -m integration -q` passed with 54 tests.
- `uv run pytest src/aeat/application/overview/tests/test_calendar.py src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py src/aeat/application/live/tests/test_filed_bulk_capture.py src/aeat/application/live/tests/test_justificante_capture.py src/aeat/application/live/tests/test_justificante_capture_resolution.py src/aeat/application/live/tests/test_justificante_reconcile_from_persisted.py src/aeat/application/modelo/tests/test_import_flow.py src/aeat/application/calculations/tests/test_cross_period_clean_state.py src/aeat/entrypoints/cli/tests/test_live_read_subgroups.py src/aeat/entrypoints/cli/tests/test_live_justificante_verbs.py src/aeat/entrypoints/cli/tests/test_registry_cli.py src/aeat/entrypoints/cli/tests/test_json_schema_conformance.py src/aeat/entrypoints/cli/tests/test_documented_command_conformance.py -m "integration or not integration" -q` passed with 440 tests.

Live verification under a fresh S15 file-backed profile proved profile creation, profile status, and `app overview calendar --from 2026-01-01 --to 2026-12-31 --allow-incomplete`. The calendar returned Modelo 100/303/390/721 entries with local filing readiness separate from AEAT submission state and justificante verification.

The authenticated Modelo 036/G313 censo reconciliation remains open because `config profile censo pull` correctly refused live AEAT auth when the Cl@ve identity did not match the active profile tax identity. This is the right fail-closed behavior, but it leaves final censo-derived obligation proof blocked until the operator authenticates with a matching taxpayer profile.
