---
tags:
  - '#exec'
  - '#live-pull-verification-sweep'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S27'
related:
  - '[[2026-06-12-live-pull-verification-sweep-plan]]'
  - '[[2026-06-05-calendar-filing-semantics-adr]]'
---

# W03.P06.S27 - calendar local/AEAT filing axis preservation

## Description

- Re-grounded the remaining calendar/modelo evidence gap with `vaultspec-rag search --timeout 900` against calendar `ModeloRecord`, `aeat_accepted`, `external_evidence`, filed history, justificantes, and cross-period state.
- Tightened the overview calendar projection so `ModeloRecord.external_evidence` no longer overwrites the local application filing axis.
- Local records filed by the normal app remain `local_filing_state=ready_to_file` even after live AEAT evidence is attached by filed-history or justificante enrollment.
- External baseline imports created through the `aeat-import` actor remain `local_filing_state=external_baseline_imported`.
- Updated focused calendar tests so live AEAT capture evidence proves the AEAT axis while preserving the local ready-to-file axis, and imported baseline tests explicitly use the import actor.

## Outcome

The calendar now represents both user-facing meanings of "filing" at the same time:

- The application-side condition that a Modelo calculation has been locally filed/current and is therefore ready/current in the app.
- The real-world AEAT condition that the return has been observed as submitted, accepted, or justificante-verified.

This prevents an AEAT evidence stamp from making a locally prepared Modelo look like a purely external baseline import.

## Verification

- `uv run vaultspec-rag search --timeout 900 "calendar ModeloRecord aeat_accepted external_evidence filed history justificante local ready filed submitted calendar event cross period"` returned the calendar filing semantics ADR, external-evidence calendar proof, and cross-period justificante verification references.
- `uv run ruff check src/aeat/application/overview/_calendar.py src/aeat/application/overview/tests/test_calendar.py src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py` passed.
- `TMP=Y:\tmp\aeat-pytest TEMP=Y:\tmp\aeat-pytest uv run pytest src/aeat/application/overview/tests/test_calendar.py src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py -m "integration or not integration" -q` passed with 78 tests.
- `TMP=Y:\tmp\aeat-pytest TEMP=Y:\tmp\aeat-pytest uv run pytest src/aeat/application/live/tests/test_filed_capture_calculation_history.py src/aeat/application/calculations/tests/test_cross_period_clean_state.py src/aeat/application/overview/tests/test_calendar.py src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py -m "integration or not integration" -q` passed with 128 tests.
- `TMP=Y:\tmp\aeat-pytest TEMP=Y:\tmp\aeat-pytest uv run pytest src/aeat/entrypoints/cli/tests/test_registry_cli.py -k "filed or pull_evidence_resolves_target_period" -m "integration or not integration" -q` passed with 12 selected tests.

## Notes

- This is local/backend calendar proof. Authenticated live AEAT exercise still requires a matching taxpayer identity and a valid 8+ character secret-store passphrase for the fresh live profile.
