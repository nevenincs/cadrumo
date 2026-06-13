---
tags:
  - '#exec'
  - '#live-censo-calendar-reconciliation'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S22'
related:
  - '[[2026-06-05-live-censo-calendar-reconciliation-plan]]'
---

# W05.P05.S22 - store-verified filed-declaration justificante evidence

## Description

- Require filed-declaration justificante artefact storage refs to be explicitly verified before calendar projection can mark `justificante_verified`.
- Thread verified artefact refs from the overview CLI storage loader into `calendar_filing_evidence_from_sources`.
- Keep dangling or unverified filed-declaration justificante manifests as `submitted_observed`.
- Preserve expediente-specific event enrichment while refusing manifest-only verification.

## Outcome

Calendar justificante verification no longer trusts filed-declaration observation manifests alone. The storage layer must load the encrypted artefact body and verify byte count plus SHA-256, then pass the verified storage ref into the pure calendar projection. Without that proof, the calendar can still show an AEAT observed submission, but it does not claim justificante verification.

## Verification

- `uv run ruff check src/aeat/application/overview/_calendar.py src/aeat/entrypoints/cli/_overview.py src/aeat/application/overview/tests/test_calendar.py src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py` passed.
- `uv run pytest src/aeat/application/overview/tests/test_calendar.py src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py -m "integration or not integration" -q` passed with 71 tests.
- `uv run ruff check src/aeat/application/calculations/_observations_repository.py src/aeat/application/live/_filed_observation_persistence.py src/aeat/application/overview/_calendar.py src/aeat/entrypoints/cli/_overview.py src/aeat/application/calculations/_cross_period_clean_state.py src/aeat/application/calculations/tests/test_observations_repository_roundtrip.py src/aeat/application/live/tests/test_filed_capture_calculation_history.py src/aeat/application/overview/tests/test_calendar.py src/aeat/application/calculations/tests/test_cross_period_clean_state.py src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py src/aeat/entrypoints/cli/tests/test_registry_cli.py` passed.
- `uv run pytest src/aeat/application/calculations/tests/test_observations_repository_roundtrip.py src/aeat/application/live/tests/test_filed_capture_calculation_history.py src/aeat/application/overview/tests/test_calendar.py src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py src/aeat/application/calculations/tests/test_cross_period_clean_state.py src/aeat/entrypoints/cli/tests/test_registry_cli.py -m "integration or not integration" -q` passed with 174 tests.
- `vaultspec-code-reviewer` reviewed S22 and reported no findings.

## Notes

Live profile-bound verification remains blocked before AEAT authentication in this shell because `AEAT_SECRET_PASSPHRASE` is unset and no `AEAT*` environment variables are available. The live pull sequence still needs a valid profile passphrase and a profile tax identity matching the Cl@ve identity.
