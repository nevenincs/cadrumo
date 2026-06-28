---
tags:
  - '#exec'
  - '#live-pull-verification-sweep'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S27'
related:
  - '[[2026-06-12-live-pull-verification-sweep-plan]]'
  - '[[2026-06-12-live-pull-verification-sweep-w02-p04-s10-w03-p05-s19-censo-enrolment-key-centralisation-exec]]'
---

# W03.P06.S27 / W04.P07.S29 censo all-required calendar provenance

## Scope

Hardened the overview calendar censo provenance warning so a Modelo calendar
obligation is cleared only when every censo-relevant enrolment key for that
Modelo has live Modelo 036 / censo provenance. This preserves the distinction
between a locally modelled ready-to-file obligation and a real-world AEAT
submission or censo-confirmed enrolment state.

## Description

- Require the calendar censo warning to compare the full required key set
  against live-censo verified profile keys instead of accepting any one
  matching key.
- Add unit coverage proving Modelo 303 remains warned when `iva.regime` is
  missing from censo provenance even if the other Modelo 303 enrolment facts
  are verified.
- Add unit coverage proving Modelo 303 clears when `activities.iae_epigraph`,
  `iva.regime`, `taxpayer_type.entity_type`, and
  `taxpayer_type.irpf_income_categories` are all verified.
- Add the missing corporate censo enrolment key mapping for Modelos 200 and
  202, after code review found that the centralized corporate keys could not
  be required by the per-Modelo warning path.
- Add unit coverage proving Modelo 202 remains warned when any required
  corporate censo key is missing and clears only when entity type, legal form,
  INCN, and new-entity-first-two-profit-periods provenance are all present.
- Update the censo-stamped CLI calendar fixture to stamp `iva.regime` from
  censo so the stricter calendar rule reflects the live Modelo 036 source set.
- Re-check the CLI verb drift guard: only negative `pull-all` tests and plan
  text reference `pull-all`; live acquisition remains under `pull`.

## Outcome

Changed code:

- `src/aeat/application/overview/_calendar.py`
- `src/aeat/application/overview/tests/test_calendar.py`
- `src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py`

Verification:

- `vaultspec-rag search "calendar censo enrolment warning all required profile keys" --type code --port 8766 --max-results 12 --timeout 60`
  - result: `http_search_timeout`; RAG service was healthy, so exact local
    symbol discovery continued with `rg`.
- `vaultspec-rag search "corporate censo enrolment legal entity form modelo 200 202 calendar applicability" --type code --port 8766 --max-results 12 --timeout 60`
  - result: `http_search_timeout`; exact local symbol discovery continued
    with `rg`.
- `.venv\Scripts\python.exe -m ruff check src/aeat/application/overview/_calendar.py src/aeat/application/overview/tests/test_calendar.py src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py`
  - result: passed.
- `.venv\Scripts\python.exe -m pytest -m unit src/aeat/application/overview/tests/test_calendar.py::test_calendar_censo_warning_requires_every_modelo_enrolment_key src/aeat/application/overview/tests/test_calendar.py::test_calendar_censo_warning_clears_when_every_modelo_enrolment_key_is_verified -q -rs --tb=short`
  - result: 2 passed.
- `.venv\Scripts\python.exe -m pytest -m unit src/aeat/application/overview/tests/test_calendar.py::test_calendar_censo_warning_requires_corporate_modelo_202_enrolment_keys src/aeat/application/overview/tests/test_calendar.py::test_calendar_censo_warning_clears_for_complete_corporate_modelo_202_provenance -q -rs --tb=short`
  - result: 2 passed.
- `.venv\Scripts\python.exe -m pytest -m unit src/aeat/application/overview/tests/test_calendar.py -q -rs --tb=short`
  - result: 75 passed.
- `.venv\Scripts\python.exe -m pytest -m "integration and hex_entrypoint" src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py::test_calendar_accepts_censo_stamped_enrolment src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py::test_calendar_blocks_profile_derived_enrolment_without_live_censo -q -rs --tb=short`
  - result: 2 passed.
- `.venv\Scripts\python.exe -m pytest -m "integration and hex_entrypoint" src/aeat/entrypoints/cli/tests/test_profile_censo_verbs.py -q -rs --tb=short`
  - result: 11 passed.
- `.venv\Scripts\python.exe -m pytest -m "integration and hex_entrypoint" src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py -q -rs --tb=short`
  - result: 15 passed.
- `.venv\Scripts\python.exe -m pytest -m "integration and hex_entrypoint" src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_filed_pull_cli_help_supports_bulk_options_without_pull_all src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_expedientes_pull_cli_help_supports_bulk_options_without_pull_all src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_command_tree_rejects_pull_all_and_capture_all_aliases src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_filed_bulk_pull_text_reports_failures_without_pull_all -q -rs --tb=short`
  - result: 4 passed.

## Notes

This is local calendar/censo hardening and focused gate evidence. It does not
close the live-authenticated censo/filed/justificante rows: positive AEAT
Modelo 036/censo pull evidence, filed-history evidence, and verified
justificante pulls still need an operator-authenticated live run before
`W02.P04.S10`, `W03.P05.S19`, or `W03.P06.S27` can be checked complete.
