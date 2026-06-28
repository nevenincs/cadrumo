---
tags:
  - '#exec'
  - '#live-censo-calendar-reconciliation'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S23'
related:
  - '[[2026-06-05-live-censo-calendar-reconciliation-plan]]'
---

# W05.P05.S23 - live justificante capture stamping matches current filing

## Description

- Refuse `AEAT_LIVE_CAPTURE` evidence stamping unless the parsed live justificante matches the current filing record.
- Match modelo, filing year, typed `Period`, and taxpayer identity before saving the justificante or marking the filing accepted.
- Resolve the expected taxpayer from member NIF for member filings, otherwise from the active profile record.
- Add real-PDF regressions for modelo, filing-year, period, and taxpayer mismatches.

## Outcome

`register_capture_as_filing_evidence` now parses the persisted capture before saving evidence and refuses when the receipt does not describe the same filing record. The refusal happens before `JustificanteRepository().save`, before `external_evidence = AEAT_LIVE_CAPTURE`, before `aeat_accepted = true`, and before the live-evidence bucket event.

The tests use the real Modelo 130 2026 Q1 justificante fixture and the production parser. They prove mismatched modelo, year, period, and profile tax identity do not create a justificante record and do not mark the local filing as AEAT accepted.

## Verification

- `uv run ruff check src/aeat/application/live/_justificante.py src/aeat/application/live/tests/test_justificante_reconcile_from_persisted.py` passed.
- `uv run pytest src/aeat/application/live/tests/test_justificante_reconcile_from_persisted.py -q` passed with 11 tests.
- `uv run ruff check src/aeat/application/live/_justificante.py src/aeat/application/live/tests/test_justificante_reconcile_from_persisted.py src/aeat/application/calculations/_cross_period_clean_state.py src/aeat/application/calculations/tests/test_cross_period_clean_state.py src/aeat/application/overview/_calendar.py src/aeat/application/overview/tests/test_calendar.py src/aeat/entrypoints/cli/_overview.py src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py src/aeat/entrypoints/cli/tests/test_registry_cli.py` passed.
- `uv run pytest src/aeat/application/live/tests/test_justificante_reconcile_from_persisted.py src/aeat/application/calculations/tests/test_cross_period_clean_state.py src/aeat/application/overview/tests/test_calendar.py -q` passed with 101 tests.
- `uv run pytest src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py src/aeat/entrypoints/cli/tests/test_registry_cli.py -m integration -q` passed with 63 tests.
- `vaultspec-code-reviewer` reviewed S23/S24 and reported no findings; the noted residual year/period test gap was resolved before closeout.

## Live Verification

Fresh isolated profile verification under `var/live-user-smoke/20260612-s23` reached the authenticated live justificante surface. `aeat app live justificante pull --modelo 303 --year 2026 --period 1T` refused because no filed declaration exists for the target period, which correctly leaves `justificante_verified = false`.
