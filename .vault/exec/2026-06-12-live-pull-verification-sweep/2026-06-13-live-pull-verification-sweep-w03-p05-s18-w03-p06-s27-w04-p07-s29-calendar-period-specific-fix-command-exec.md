---
tags:
  - '#exec'
  - '#live-pull-verification-sweep'
date: '2026-06-13'
modified: '2026-06-13'
step_id: 'S18,S27,S29'
related:
  - '[[2026-06-12-live-pull-verification-sweep-plan]]'
  - '[[2026-06-12-live-pull-verification-sweep-code-review-audit]]'
---

# W03.P05.S18 / W03.P06.S27 / W04.P07.S29 calendar period-specific fix command

## Scope

Hardened calendar remediation for AEAT filing evidence warnings so a single
unverified or conflicting filing row points the operator at the exact read-only
filed-history pull needed for that Modelo, filing year, and typed `core.Period`.

## Description

- Changed the generic justificante and AEAT-evidence-conflict warning command
  template to include `--period PERIOD`.
- Added calendar helper logic that emits a concrete command such as
  `aeat app live filed pull --modelo 303 --year 2025 --period 1T` when exactly
  one affected typed calendar row needs remediation.
- Preserved a generic fallback command when one warning spans multiple periods,
  so the calendar does not imply that a single pull remediates every affected
  row.
- Kept acquisition under the existing `pull` verb. No `pull-all` or
  write-shaped command was introduced.

## Verification

- `vaultspec-rag -t . search --timeout 300 "live-pull-verification-sweep open gap justificante enrolment calendar modelo filing cross period filed state"`
  - result: returned the active live-pull index, row-level censo audit, and
    open live-auth blocker references.
- `uv run ruff check src/aeat/application/overview/_calendar.py src/aeat/application/overview/tests/test_calendar_filing_evidence.py src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py`
  - result: passed.
- `uv run pytest src/aeat/application/overview/tests/test_calendar_filing_evidence.py::test_calendar_warns_when_aeat_submission_lacks_verified_justificante src/aeat/application/overview/tests/test_calendar_filing_evidence.py::test_calendar_uses_generic_justificante_fix_when_multiple_periods_need_pull src/aeat/application/overview/tests/test_calendar_filing_evidence.py::test_calendar_entry_warns_when_local_and_filed_history_aeat_references_disagree -q --tb=short`
  - result: 3 passed.
- `uv run pytest -m "" src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py::test_calendar_strict_mode_refuses_unverified_aeat_filing src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py::test_calendar_strict_mode_refuses_conflicting_aeat_evidence_references src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py::test_calendar_strict_mode_refuses_imported_csv_register_without_justificante -q --tb=short`
  - result: 3 passed.
- `uv run pytest src/aeat/application/overview/tests/test_calendar_filing_evidence.py -q`
  - result: 51 passed.
- `uv run pytest -m "" src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py -q`
  - result: 19 passed.
- `uv run pytest -m "" src/aeat/application/overview/tests/test_calendar.py src/aeat/application/overview/tests/test_calendar_filing_evidence.py src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py src/aeat/entrypoints/cli/tests/test_registry_cli.py -q --tb=short`
  - result: 171 passed.

## Live run status

The visible live runner still waits at the secure-storage passphrase prompt.
This exec record is local calendar remediation hardening and does not claim a
new authenticated AEAT read.
