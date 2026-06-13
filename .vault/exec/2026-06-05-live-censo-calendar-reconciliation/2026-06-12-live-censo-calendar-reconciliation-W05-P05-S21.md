---
tags:
  - '#exec'
  - '#live-censo-calendar-reconciliation'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S21'
related:
  - '[[2026-06-05-live-censo-calendar-reconciliation-plan]]'
---

# W05.P05.S21 - calendar AEAT register provenance enforcement

## Description

- Refuse `aeat_sede_justificante` calculation observations without encrypted AEAT register provenance when projecting calendar filing evidence.
- Require projected official calculation-observation evidence to carry `ALTA` AEAT register status.
- Require stamped authenticated identity to match the rendered taxpayer when a taxpayer identity is expected.
- Keep AEAT events and filed-declaration observations visible through their existing paths without upgrading invalid calculation observations into obligation evidence.

## Outcome

Calendar filing evidence now matches the cross-period clean-state provenance rule: official calculation observations must prove active AEAT register state and taxpayer identity before they can mark an obligation as AEAT-submitted. Missing metadata, non-`ALTA` metadata, and missing or mismatched authenticated identity no longer create calendar submission evidence.

## Verification

- `uv run ruff check src/aeat/application/overview/_calendar.py src/aeat/application/overview/tests/test_calendar.py src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py` passed.
- `uv run pytest src/aeat/application/overview/tests/test_calendar.py src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py -m "integration or not integration" -q` passed with 70 tests.
- `uv run ruff check src/aeat/application/calculations/_observations_repository.py src/aeat/application/live/_filed_observation_persistence.py src/aeat/application/overview/_calendar.py src/aeat/application/calculations/_cross_period_clean_state.py src/aeat/application/calculations/tests/test_observations_repository_roundtrip.py src/aeat/application/live/tests/test_filed_capture_calculation_history.py src/aeat/application/overview/tests/test_calendar.py src/aeat/application/calculations/tests/test_cross_period_clean_state.py src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py src/aeat/entrypoints/cli/tests/test_registry_cli.py` passed.
- `uv run pytest src/aeat/application/calculations/tests/test_observations_repository_roundtrip.py src/aeat/application/live/tests/test_filed_capture_calculation_history.py src/aeat/application/overview/tests/test_calendar.py src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py src/aeat/application/calculations/tests/test_cross_period_clean_state.py src/aeat/entrypoints/cli/tests/test_registry_cli.py -m "integration or not integration" -q` passed with 173 tests.
- `vaultspec-code-reviewer` rechecked S21 and reported no findings.

## Notes

Live profile-bound verification remains blocked before AEAT authentication in this shell because `AEAT_SECRET_PASSPHRASE` is unset and no other `AEAT*` environment variable is present. The live pull sequence still needs a valid profile passphrase and a profile tax identity matching the Cl@ve identity.
