---
tags:
  - '#exec'
  - '#live-censo-calendar-reconciliation'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S18'
related:
  - '[[2026-06-05-live-censo-calendar-reconciliation-plan]]'
---

# W05.P05.S18 - active AEAT status for official filed-observation history

## Description

- Refuse direct persistence of non-`ALTA` filed AEAT observations into calculation history.
- Rank bulk filed-observation persistence by active AEAT status before timestamp and expediente id.
- Apply the same active-status ranking to IVA compensation history persistence.
- Skip non-`ALTA`-only IVA periods without failing live acquisition or writing official history.
- Add live application tests proving non-`ALTA` observations cannot become official calculation or IVA history.

## Outcome

Live filed-observation persistence now shares the active-status boundary used by declaration selection and calendar projection. A later `BAJA` or otherwise non-current AEAT register row can no longer overwrite an older `ALTA` row in official `aeat_sede_justificante` calculation history or IVA compensation history.

This protects cross-period filing gates from using stale or cancelled AEAT register rows as official source data. The strict IVA history path preserves live acquisition behavior by ignoring non-current-only periods instead of raising after the raw observation has been captured.

## Notes

Verification passed:

- `uv run ruff check src/aeat/application/live/_filed_observation_persistence.py src/aeat/application/live/tests/test_filed_capture_calculation_history.py`
- `uv run pytest src/aeat/application/live/tests/test_filed_capture_calculation_history.py -q` passed with 14 tests.
- `uv run pytest src/aeat/application/overview/tests/test_calendar.py src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py src/aeat/application/live/tests/test_filed_capture_calculation_history.py src/aeat/application/live/tests/test_filed_bulk_capture.py src/aeat/application/live/tests/test_justificante_capture.py src/aeat/application/live/tests/test_justificante_capture_resolution.py src/aeat/application/live/tests/test_justificante_reconcile_from_persisted.py src/aeat/application/modelo/tests/test_import_flow.py src/aeat/application/calculations/tests/test_cross_period_clean_state.py src/aeat/entrypoints/cli/tests/test_live_read_subgroups.py src/aeat/entrypoints/cli/tests/test_live_justificante_verbs.py src/aeat/entrypoints/cli/tests/test_registry_cli.py src/aeat/entrypoints/cli/tests/test_json_schema_conformance.py src/aeat/entrypoints/cli/tests/test_documented_command_conformance.py -m "integration or not integration" -q` passed with 459 tests.
- `vaultspec-code-reviewer` initially found a HIGH failure-mode issue in the strict IVA path for non-`ALTA`-only periods; the fix was applied and re-review returned no findings.

The live Modelo 036/G313 censo-derived obligation proof remains open until a matching taxpayer profile authenticates successfully. Historical `aeat_sede_justificante` calculation observations persisted before this guard may lack original AEAT status metadata; this is a pre-existing data hygiene risk outside the S18 write-path fix.
