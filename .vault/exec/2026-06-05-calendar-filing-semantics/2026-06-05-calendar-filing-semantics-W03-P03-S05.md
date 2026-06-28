---
tags:
  - '#exec'
  - '#calendar-filing-semantics'
date: '2026-06-11'
modified: '2026-06-11'
step_id: 'S05'
related:
  - '[[2026-06-05-calendar-filing-semantics-plan]]'
---

# `calendar-filing-semantics` `W03.P03.S05` exec - taxpayer-bound justificante verification

## Scope

Step `W03.P03.S05` - Bind calendar justificante verification to persisted metadata and active taxpayer; `src/aeat/application/overview/_calendar.py`, `src/aeat/entrypoints/cli/_overview.py`, `src/aeat/application/overview/tests/test_calendar.py`, `src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py`.

## Description

- Require `calendar_filing_evidence_from_sources` to receive loaded justificante metadata and an expected taxpayer tax ID before Modelo-record external evidence can become `justificante_verified`.
- Keep local Modelo records with external evidence as `external_baseline_imported`, while downgrading unbound `aeat_justificante_pdf` and `aeat_live_capture` evidence to accepted or submitted-observed AEAT states.
- Load `JustificanteRepository` metadata inside the overview CLI profile storage session and pass the active or iterated profile tax ID into the calendar evidence merger.
- Accept typed `Period` objects from the deadline engine in the overview calendar period bridge after backend drift changed the obligation period representation.
- Add application and storage-backed CLI regressions for persisted justificante verification, missing metadata, wrong-taxpayer metadata, and wrong Modelo/year/period metadata.

## Outcome

- `uv run pytest src/aeat/application/overview/tests/test_calendar.py -q` passed: 51 passed.
- `uv run pytest src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py -m integration -q` passed: 9 passed.
- `uv run ruff check src/aeat/application/overview/_calendar.py src/aeat/entrypoints/cli/_overview.py src/aeat/application/overview/tests/test_calendar.py src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py` passed.

## Notes

- `vaultspec-core vault plan wave add`, `phase add`, `step add`, and `step check` persisted their mutations but exited with a cache-invalidation `LookupError` because the CLI workspace context was unset. Subsequent `vaultspec-core vault plan status`, `query`, and `check` confirmed the plan structure and checked step state.
