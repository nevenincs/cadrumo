---
tags: ['#exec', '#live-pull-verification-sweep']
date: '2026-06-13'
modified: '2026-06-13'
step_id: 'S18,S27,S29'
related:
  - '[[2026-06-12-live-pull-verification-sweep-plan]]'
  - '[[2026-06-12-live-pull-verification-sweep-code-review-audit]]'
---

# W03.P05.S18 / W03.P06.S27 / W04.P07.S29 calendar register-reference alignment

## Scope

Aligned overview-calendar official calculation-observation evidence with the
cross-period clean-state register-reference rule while keeping the active CLI
verb drift watch on `pull` versus `pull-all`.

## Description

- Require nonblank `aeat_expediente_id` before an official calculation
  observation source can render as AEAT-submitted calendar evidence.
- Add regression coverage proving an `ALTA` official observation with matching
  justificante CSV but no register/expediente reference is not shown as AEAT
  filing evidence.
- Rechecked filed and expedientes live command help so acquisition remains under
  `pull` and no production `pull-all` command is exposed.
- Started the existing isolated live-auth runner for an operator-mediated
  Cl@ve attempt against censo, filed history, expedientes, notifications,
  justificante, and calendar projection.

## Outcome

Calendar projection now refuses the same incomplete official observation shape
that cross-period clean-state refuses: `ALTA` and justificante metadata are not
enough unless the AEAT register/expediente reference is present. Local
ready-to-file `app_filing` rows remain visible only on the local axis, and
typed `core.Period` remains the matching/stringification authority for
calendar keys and fix commands.

Bulk filed and expedientes acquisition remains exposed through `pull` only.
The production help surface lists `app live filed list`, `app live filed pull`,
`app live filed pull-sources`, and `app live expedientes pull/list/view/latest`;
there is no production `pull-all` command.

## Verification

- `uv run vaultspec-rag search --timeout 180 "calendar filing AEAT submitted justificante profile modelo enrollment live pull censo 036 pull pull-all cli Period"` returned the active live-pull plan and prior calendar/filed-history exec records.
- `uv run vaultspec-rag search --timeout 180 "app_filing external evidence cross period clean state local observation AEAT justificante filing calendar"` returned the existing calendar official observation alignment and clean-state register-reference material.
- `uv run ruff check src/aeat/application/overview/_calendar.py src/aeat/application/overview/tests/test_calendar_filing_evidence.py` passed.
- `uv run pytest -m "" src/aeat/application/overview/tests/test_calendar_filing_evidence.py -q --tb=short` reported 53 passed.
- `uv run pytest -m "" src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_filed_pull_cli_help_supports_bulk_options_without_pull_all src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_command_tree_rejects_pull_all_and_capture_all_aliases src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py -q --tb=short` reported 21 passed.
- `uv run pytest -m "" src/aeat/application/overview/tests/test_calendar.py src/aeat/application/overview/tests/test_calendar_filing_evidence.py src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py -q --tb=short` reported 117 passed.
- `uv run pytest -m "" src/aeat/application/calculations/tests/test_cross_period_clean_state.py src/aeat/application/calculations/tests/test_cross_period_clean_state_provenance.py -q --tb=short` reported 47 passed.
- `uv run aeat app live filed --help` listed `list`, `pull`, and `pull-sources`.
- `uv run aeat app live expedientes --help` listed `pull`, `list`, `view`, and `latest`.
- `rg -n "pull-all|pull_all|pull all|Pull all|capture-all|capture_all" src/aeat/entrypoints/cli src/aeat/application/live src/aeat/application/overview` found only tests asserting forbidden aliases are absent.
- `uv run vaultspec-core vault plan check .vault/plan/2026-06-12-live-pull-verification-sweep-plan.md` passed.

## Notes

The live runner was launched from
`var/aeat/live-auth-run/run-live-auth-20260613-ready-auth.ps1` and is still
waiting for operator secure-storage passphrase input at
`2026-06-13T14:47:37+02:00`. This record does not claim successful live AEAT
censo, filed-history, justificante, notification, expediente, or live-backed
calendar proof.
