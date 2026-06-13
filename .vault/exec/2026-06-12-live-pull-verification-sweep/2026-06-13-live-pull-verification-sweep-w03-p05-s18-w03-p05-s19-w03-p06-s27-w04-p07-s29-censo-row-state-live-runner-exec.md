---
tags:
  - '#exec'
  - '#live-pull-verification-sweep'
date: '2026-06-13'
modified: '2026-06-13'
step_id: 'S18,S19,S27,S29'
related:
  - '[[2026-06-12-live-pull-verification-sweep-plan]]'
  - '[[2026-06-12-live-pull-verification-sweep-code-review-audit]]'
  - '[[2026-06-12-live-pull-verification-sweep-live-auth-blocker-audit]]'
---

# W03.P05.S18 / W03.P05.S19 / W03.P06.S27 / W04.P07.S29 censo row state and live runner

## Scope

Continued the authenticated calendar integration slice after the typed
`core.Period` migration landed. The goal of this slice is to make each calendar
obligation expose its own censo/Modelo 036 enrolment provenance state, keep
filed-history acquisition under the single `pull` verb, and prepare an
operator-authenticated live runner for censo, filed history, expedientes,
notifications, justificantes, and calendar projection.

## Description

- Added `OverviewCensoEnrolmentState` to the overview calendar model with
  `not_checked`, `not_required`, `unverified`, and `verified` states.
- Added `censo_enrolment_state` to every `OverviewCalendarEntry` so the calendar
  row itself reports whether the Modelo obligation is backed by live censo /
  Modelo 036 provenance.
- Reused the centralized calendar censo enrolment key logic so the row state and
  strict warning path agree: a Modelo row is `verified` only when every required
  censo-relevant profile key for that Modelo has live-censo provenance.
- Exposed `censo_enrolment_state` in the CLI JSON payload and in text calendar
  rows as `censo_enrolment=...`.
- Rechecked the period migration surface: calendar/filed evidence tests continue
  to compare typed `core.Period` values and serialize periods only at payload or
  text-output boundaries.
- Rechecked CLI verb drift: production acquisition remains under `app live filed
  pull`; the rejected `pull-all` form remains only a negative guard and operator
  refusal check.
- Created a visible read-only live runner at
  `var/aeat/live-auth-run/run-live-auth-20260613-operator.ps1`. The runner uses
  an isolated storage root, prompts for a new test-profile secure-storage
  passphrase, loads the configured Cl@ve variables without printing secrets, and
  then executes profile creation, auth login, censo pull/compare, filed
  list/pull, expedientes pull, notifications pull, justificante list, overview
  calendar projection, and the `pull-all` refusal check.

## Verification

- `vaultspec-rag -t . search --timeout 300 "live calendar censo filed history justificante core Period pull command"`
  - result: returned the active live-pull plan and adjacent audit/exec records.
- `uv run ruff check src/aeat/application/overview/_calendar.py src/aeat/application/overview/_calendar_models.py src/aeat/application/overview/__init__.py src/aeat/entrypoints/cli/_overview.py src/aeat/entrypoints/cli/_overview_payloads.py src/aeat/application/overview/tests/test_calendar.py src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py`
  - result: passed.
- `uv run pytest src/aeat/application/overview/tests/test_calendar.py -q`
  - result: 45 passed.
- `uv run pytest -m "" src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py -q`
  - result: 19 passed.
- `uv run pytest src/aeat/application/overview/tests/test_calendar_filing_evidence.py -q`
  - result: 50 passed.
- `uv run pytest -m "" src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_filed_pull_cli_help_supports_bulk_options_without_pull_all src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_command_tree_rejects_pull_all_and_capture_all_aliases -q`
  - result: 2 passed.
- `uv run pytest -m "" src/aeat/entrypoints/cli/tests/test_json_schema_conformance.py -q`
  - result: 94 passed.
- `uv run pytest -m "" src/aeat/entrypoints/cli/tests/test_live_read_subgroups.py src/aeat/entrypoints/cli/tests/test_app_live_filed_rendering.py src/aeat/entrypoints/cli/tests/test_live_justificante_verbs.py -q`
  - result: 32 passed.
- `uv run pytest src/aeat/application/live/tests/test_filed_bulk_capture.py src/aeat/application/live/tests/test_expedientes.py src/aeat/application/live/tests/test_notifications.py -q`
  - result: 37 passed.
- `uv run pytest -m "" src/aeat/entrypoints/cli/tests/test_profile_censo_verbs.py -q`
  - result: 12 passed.
- `uv run aeat app live filed pull-all --help`
  - result: failed as expected with `No such command 'pull-all'. Did you mean 'pull'?`.
- PowerShell parser check for `var/aeat/live-auth-run/run-live-auth-20260613-operator.ps1`
  - result: parsed successfully.

## Live run status

The refreshed visible runner process was started with a pre-prompt heartbeat and
redacted log at `var/aeat/live-auth-run/live-auth-20260613-operator.log`. At the
time this exec record was written, the runner had reached the secure-storage
passphrase prompt and was waiting for operator input before any authenticated
AEAT command could execute.

## Notes

This slice does not close `W02.P04.S10`, `W02.P04.S11`, `W02.P04.S14`,
`W03.P05.S18`, `W03.P05.S19`, or `W03.P06.S27`. Positive live Modelo 036/censo,
filed-row, justificante, and live-backed calendar evidence must still be
captured from the authenticated runner before those rows can be checked
complete.
