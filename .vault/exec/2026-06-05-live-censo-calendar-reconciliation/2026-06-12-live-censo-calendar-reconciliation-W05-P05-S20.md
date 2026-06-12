---
tags:
  - '#exec'
  - '#live-censo-calendar-reconciliation'
date: '2026-06-12'
step_id: 'S20'
related:
  - '[[2026-06-05-live-censo-calendar-reconciliation-plan]]'
---

# W05.P05.S20 - cross-period AEAT register provenance enforcement

## Description

- Enforce stamped AEAT register provenance on cross-period source observations.
- Block `aeat_sede_justificante` source observations that lack stamped AEAT register provenance.
- Block `aeat_sede_justificante` source observations with non-`ALTA` register status.
- Block source observations whose stamped authenticated identity does not match the taxpayer or expected group member.

## Outcome

Cross-period clean-state now treats encrypted AEAT register provenance as part of official source validity. Persisted `aeat_sede_justificante` observations must carry active AEAT status and matching identity before they can satisfy cross-period dependencies. Missing provenance, non-`ALTA` status, and mismatched authenticated identity all produce `MISMATCHED_EXTERNAL_EVIDENCE_RECORD`.

## Verification

- `uv run --no-sync ruff check src/aeat/application/calculations/_cross_period_clean_state.py src/aeat/application/calculations/_observations_repository.py src/aeat/application/live/_filed_observation_persistence.py src/aeat/application/overview/_calendar.py src/aeat/application/calculations/tests/test_cross_period_clean_state.py src/aeat/application/calculations/tests/test_observations_repository_roundtrip.py src/aeat/application/live/tests/test_filed_capture_calculation_history.py src/aeat/application/overview/tests/test_calendar.py` passed.
- `uv run --no-sync pytest src/aeat/application/calculations/tests/test_observations_repository_roundtrip.py src/aeat/application/live/tests/test_filed_capture_calculation_history.py src/aeat/application/overview/tests/test_calendar.py src/aeat/application/calculations/tests/test_cross_period_clean_state.py -q` passed with 107 tests.
- `uv run ruff check src/aeat/application/calculations/_observations_repository.py src/aeat/application/live/_filed_observation_persistence.py src/aeat/application/overview/_calendar.py src/aeat/application/calculations/_cross_period_clean_state.py src/aeat/application/calculations/tests/test_observations_repository_roundtrip.py src/aeat/application/live/tests/test_filed_capture_calculation_history.py src/aeat/application/overview/tests/test_calendar.py src/aeat/application/calculations/tests/test_cross_period_clean_state.py src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py src/aeat/entrypoints/cli/tests/test_registry_cli.py` passed.
- `uv run pytest src/aeat/application/calculations/tests/test_observations_repository_roundtrip.py src/aeat/application/live/tests/test_filed_capture_calculation_history.py src/aeat/application/overview/tests/test_calendar.py src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py src/aeat/application/calculations/tests/test_cross_period_clean_state.py src/aeat/entrypoints/cli/tests/test_registry_cli.py -m "integration or not integration" -q` passed with 171 tests.
- `vaultspec-code-reviewer` found CENSO-021, the missing-provenance bypass. The fix made empty `source_metadata` block and added a matching filing/justificante regression. Re-review passed with no CENSO-022 finding.

## Notes

Live profile-bound verification is still blocked before AEAT authentication in this shell: `AEAT_SECRET_PASSPHRASE` is unset, and the trial value `horatio` is rejected by the application because it is shorter than the 8-character verifier minimum. The live pull sequence must run with a valid profile passphrase and a profile tax identity matching the Cl@ve identity.
