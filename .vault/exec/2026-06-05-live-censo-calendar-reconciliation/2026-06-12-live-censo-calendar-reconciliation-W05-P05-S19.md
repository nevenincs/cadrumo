---
tags:
  - '#exec'
  - '#live-censo-calendar-reconciliation'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S19'
related:
  - '[[2026-06-05-live-censo-calendar-reconciliation-plan]]'
---

# W05.P05.S19 - encrypted AEAT register provenance for official observations

## Description

- Add encrypted source metadata to persisted calculation observation envelopes.
- Stamp live filed-observation calculation history with AEAT register status, expediente id, and authenticated identity.
- Project expediente ids from persisted calculation-observation metadata into calendar AEAT evidence.
- Refuse calendar evidence from persisted calculation observations whose encrypted AEAT status metadata is non-`ALTA`.

## Outcome

Official `aeat_sede_justificante` calculation observations now carry enough encrypted provenance for downstream readers to audit the AEAT register row that produced the history. New live persisted observations are no longer opaque `source_kind` rows: they retain the active AEAT status, the expediente reference, and the authenticated identity inside the secure AUDIT payload.

The calendar consumes that metadata when available. `ALTA` metadata provides the AEAT reference id, non-`ALTA` metadata refuses submission evidence, and stamped authenticated identity must match the active taxpayer before calculation-observation evidence is projected. Legacy records without this metadata continue to degrade as previously recorded historical risk.

## Notes

Verification passed:

- `uv run ruff check src/aeat/application/calculations/_observations_repository.py src/aeat/application/live/_filed_observation_persistence.py src/aeat/application/overview/_calendar.py src/aeat/application/calculations/tests/test_observations_repository_roundtrip.py src/aeat/application/live/tests/test_filed_capture_calculation_history.py src/aeat/application/overview/tests/test_calendar.py`
- `uv run pytest src/aeat/application/calculations/tests/test_observations_repository_roundtrip.py src/aeat/application/live/tests/test_filed_capture_calculation_history.py src/aeat/application/overview/tests/test_calendar.py -q` passed with 80 tests.
- `uv run pytest src/aeat/application/overview/tests/test_calendar.py src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py src/aeat/application/calculations/tests/test_observations_repository_roundtrip.py src/aeat/application/live/tests/test_filed_capture_calculation_history.py src/aeat/application/live/tests/test_filed_bulk_capture.py src/aeat/application/live/tests/test_justificante_capture.py src/aeat/application/live/tests/test_justificante_capture_resolution.py src/aeat/application/live/tests/test_justificante_reconcile_from_persisted.py src/aeat/application/modelo/tests/test_import_flow.py src/aeat/application/calculations/tests/test_cross_period_clean_state.py src/aeat/entrypoints/cli/tests/test_live_read_subgroups.py src/aeat/entrypoints/cli/tests/test_live_justificante_verbs.py src/aeat/entrypoints/cli/tests/test_registry_cli.py src/aeat/entrypoints/cli/tests/test_json_schema_conformance.py src/aeat/entrypoints/cli/tests/test_documented_command_conformance.py -m "integration or not integration" -q` passed with 468 tests.
- `vaultspec-code-reviewer` initially found a HIGH issue where stamped `authenticated_identity` was not enforced in calendar calculation-observation projection; the fix was applied and re-review returned no findings.

The live Modelo 036/G313 censo-derived obligation proof remains open until a matching taxpayer profile authenticates successfully.
