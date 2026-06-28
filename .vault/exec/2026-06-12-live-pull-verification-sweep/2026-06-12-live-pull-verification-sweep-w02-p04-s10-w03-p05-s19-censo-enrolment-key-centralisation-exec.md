---
tags:
  - '#exec'
  - '#live-pull-verification-sweep'
date: '2026-06-12'
modified: '2026-06-12'
plan: '[[2026-06-12-live-pull-verification-sweep-plan]]'
step_id: W03.P05.S19
related_steps:
  - W02.P04.S10
  - W03.P06.S27
  - W04.P07.S29
---

# W03.P05.S19 censo enrolment key centralisation

## Scope

Centralised the censo enrolment profile-key set under the overview calendar
application surface and switched `config profile censo apply` to consume that
calendar-owned authority.

This prevents the censo apply summary from drifting away from the calendar
warning engine. The earlier IVA-regime provenance alignment is now durable:
`iva.regime` is owned by the same key set that drives
`censo.enrolment_unverified`.

## Code changes

- `src/aeat/application/overview/_calendar.py`
  - added `calendar_censo_enrolment_profile_keys()`.
- `src/aeat/application/overview/__init__.py`
  - re-exported `calendar_censo_enrolment_profile_keys`.
- `src/aeat/entrypoints/cli/_config/_profile_censo.py`
  - replaced the local censo enrolment key copy with the overview application
    export.
- `src/aeat/application/overview/tests/test_calendar.py`
  - added a unit test pinning the centralised key set, including
    `iva.regime`.

## Verification

Required semantic discovery was attempted first:

- `vaultspec-rag search --timeout 180 "calendar censo enrolment profile keys central authority iva regime cli apply provenance"`
  - result: `http_search_timeout`.

Focused gates:

- `.venv\Scripts\python.exe -m ruff check src/aeat/application/overview/_calendar.py src/aeat/application/overview/__init__.py src/aeat/application/overview/tests/test_calendar.py src/aeat/entrypoints/cli/_config/_profile_censo.py src/aeat/entrypoints/cli/tests/test_profile_censo_verbs.py`
  - result: passed.
- `.venv\Scripts\python.exe -m pytest -m unit src/aeat/application/overview/tests/test_calendar.py::test_calendar_censo_enrolment_profile_keys_are_centralised -q -rs --tb=short`
  - result: 1 passed.
- `.venv\Scripts\python.exe -m pytest -m "integration and hex_entrypoint" src/aeat/entrypoints/cli/tests/test_profile_censo_verbs.py::test_apply_writes_censo_facts_onto_profile src/aeat/entrypoints/cli/tests/test_profile_censo_verbs.py::test_apply_emits_json_payload_with_written_paths -q -rs --tb=short`
  - result: 2 passed.
- `.venv\Scripts\python.exe -m pytest -m unit src/aeat/application/overview/tests/test_calendar.py -q -rs --tb=short`
  - result: 71 passed.
- `.venv\Scripts\python.exe -m pytest -m "integration and hex_entrypoint" src/aeat/entrypoints/cli/tests/test_profile_censo_verbs.py -q -rs --tb=short`
  - result: 11 passed.

## Plan status

This is local censo/calendar hardening. It does not close the live censo rows:
positive authenticated Modelo 036/censo pull evidence is still required before
`W02.P04.S10`, `W03.P05.S19`, or `W03.P06.S27` can close.
