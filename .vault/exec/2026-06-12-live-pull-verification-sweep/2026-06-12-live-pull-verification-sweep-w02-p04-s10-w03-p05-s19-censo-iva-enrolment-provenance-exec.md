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

# W03.P05.S19 censo IVA enrolment provenance

## Scope

Aligned `config profile censo apply` calendar-enrolment reporting with the
calendar warning engine for IVA obligations.

The calendar censo reconciliation warning treats `iva.regime` as an enrolment
profile key for IVA modelos. Censo apply can also persist `iva.regime` directly
from the Modelo 036/censo snapshot as `aeat_censo_read`. The CLI apply summary
now reports that provenance in:

- `calendar_enrolment_source_paths`;
- per-row `calendar_obligation_rows[*].enrolment_source_paths`;
- text output `calendar_enrolment_sources`;
- text output `calendar_obligation ... enrolment_sources=...`.

## Code changes

- `src/aeat/entrypoints/cli/_config/_profile_censo.py`
  - added `iva.regime` to `_calendar_enrolment_source_paths`.
- `src/aeat/entrypoints/cli/tests/test_profile_censo_verbs.py`
  - the censo snapshot fixture now includes `iva.regime=GENERAL` when it
    captures the IAE epigraph used for calendar derivation;
  - text and JSON apply assertions require `iva.regime=aeat_censo_read` in
    global calendar enrolment sources and Modelo 303 obligation rows;
  - Modelo 100 rows remain scoped to `taxpayer_type.entity_type`, proving row
    source lists still use applicability-specific keys.

## Verification

Required semantic discovery was attempted first:

- `vaultspec-rag search --timeout 180 "censo Modelo 036 calendar enrolment provenance iva regime obligation verification justificante"`
  - result: `http_search_timeout`.

Focused gates:

- `.venv\Scripts\python.exe -m ruff check src/aeat/entrypoints/cli/_config/_profile_censo.py src/aeat/entrypoints/cli/tests/test_profile_censo_verbs.py`
  - result: passed.
- `.venv\Scripts\python.exe -m pytest -m "integration and hex_entrypoint" src/aeat/entrypoints/cli/tests/test_profile_censo_verbs.py::test_apply_writes_censo_facts_onto_profile src/aeat/entrypoints/cli/tests/test_profile_censo_verbs.py::test_apply_emits_json_payload_with_written_paths -q -rs --tb=short`
  - result: 2 passed.
- `.venv\Scripts\python.exe -m pytest -m "integration and hex_entrypoint" src/aeat/entrypoints/cli/tests/test_profile_censo_verbs.py -q -rs --tb=short`
  - result: 11 passed.
- `.venv\Scripts\python.exe -m pytest -m "integration and hex_entrypoint" src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py::test_calendar_accepts_censo_stamped_enrolment src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py::test_calendar_blocks_profile_derived_enrolment_without_live_censo -q -rs --tb=short`
  - result: 2 passed.
- `.venv\Scripts\python.exe -m pytest -m unit src/aeat/application/user_profile/tests/test_censo_sync.py::test_apply_derives_taxpayer_axes_from_nie_and_iae_for_calendar -q -rs --tb=short`
  - result: 1 passed.

## Plan status

This improves censo-to-calendar provenance reporting and local CLI coverage. It
does not close `W02.P04.S10`, `W03.P05.S19`, or `W03.P06.S27` because a positive
authenticated Modelo 036/censo pull from AEAT still has to complete.
