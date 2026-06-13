---
tags:
  - '#exec'
  - '#calendar-filing-semantics'
date: '2026-06-11'
modified: '2026-06-11'
step_id: 'S06'
related:
  - '[[2026-06-05-calendar-filing-semantics-plan]]'
---

# `calendar-filing-semantics` `W03.P03.S06` exec - live filed taxpayer binding

## Scope

Step `W03.P03.S06` - Bind live filed-declaration evidence to authenticated taxpayer identity; `src/aeat/application/overview/_calendar.py`, `src/aeat/application/overview/tests/test_calendar.py`.

## Description

- Threaded `expected_tax_id` into filed-declaration observation projection inside `calendar_filing_evidence_from_sources`.
- Refused filed-declaration observations whose `authenticated_identity` does not match the rendered taxpayer when the caller supplies an expected tax ID.
- Added a regression proving a loadable `justificante_pdf` artefact for another authenticated identity does not attach any AEAT filing evidence to this taxpayer's calendar.

## Outcome

- `uv run pytest src/aeat/application/overview/tests/test_calendar.py -q` passed: 52 passed.
- `uv run pytest src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py -m integration -q` passed: 9 passed.
- `uv run ruff check src/aeat/application/overview/_calendar.py src/aeat/application/overview/tests/test_calendar.py src/aeat/entrypoints/cli/_overview.py src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py` passed.

## Notes

- Existing direct pure-function callers that do not provide `expected_tax_id` keep their prior behavior. Production overview CLI paths already pass the active or iterated profile tax ID.
- `vaultspec-core vault plan step add/check` persisted the step state but exited with the known cache-invalidation `LookupError` caused by an unset vault CLI workspace context.
