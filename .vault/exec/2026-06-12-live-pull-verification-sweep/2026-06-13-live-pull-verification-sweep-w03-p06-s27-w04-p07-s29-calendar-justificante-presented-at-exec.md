---
tags:
  - '#exec'
  - '#live-pull-verification-sweep'
date: '2026-06-13'
modified: '2026-06-13'
step_id: 'S27,S29'
related:
  - '[[2026-06-12-live-pull-verification-sweep-plan]]'
  - '[[2026-06-12-live-pull-verification-sweep-code-review-audit]]'
---

# W03.P06.S27 / W04.P07.S29 calendar justificante presented-at

## Scope

Carried the official AEAT presentation timestamp from matched justificante
metadata into the calendar filing-evidence row for Modelo filing records.

## Description

- Updated Modelo-record calendar evidence so a verified matching justificante
  sets `aeat_submitted_at` from the receipt's `presented_at` timestamp.
- Kept unverified AEAT evidence from using local import/capture time as an
  official filing timestamp.
- Rendered `aeat_submitted_at` in overview calendar text output when present,
  so operators can see the real AEAT filing time alongside the local
  ready-to-file axis and justificante verification axis.
- Added regression coverage that verified evidence carries the receipt
  timestamp, while accepted-but-unverified evidence leaves the official filing
  timestamp empty.

## Outcome

The calendar now distinguishes the local application filing time from the
official AEAT filing time for the Modelo-record path when justificante metadata
proves the submission. This moves the calendar closer to the requested
local-ready-versus-real-AEAT-filed distinction without inventing official dates
for unverified evidence.

## Verification

- `uv run ruff check src/aeat/application/overview/_calendar.py src/aeat/entrypoints/cli/_overview.py src/aeat/application/overview/tests/test_calendar_filing_evidence.py src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py`
  - result: passed.
- `uv run pytest src/aeat/application/overview/tests/test_calendar_filing_evidence.py::test_live_capture_external_evidence_requires_persisted_justificante_to_verify src/aeat/application/overview/tests/test_calendar_filing_evidence.py::test_live_capture_external_evidence_without_metadata_is_not_justificante_verified -q --tb=short`
  - result: 2 passed.
- `uv run pytest -m "" src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py::test_calendar_text_output_names_verified_aeat_evidence -q --tb=short`
  - result: 1 passed.
- `uv run pytest src/aeat/application/overview/tests/test_calendar_filing_evidence.py -q --tb=short`
  - result: 51 passed.
- `uv run pytest -m "" src/aeat/application/overview/tests/test_calendar.py src/aeat/application/overview/tests/test_calendar_filing_evidence.py src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py src/aeat/entrypoints/cli/tests/test_registry_cli.py -q --tb=short`
  - result: 171 passed.
- `uv run pytest -m "" src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_filed_pull_cli_help_supports_bulk_options_without_pull_all src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_expedientes_pull_cli_help_supports_bulk_options_without_pull_all src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_command_tree_rejects_pull_all_and_capture_all_aliases -q --tb=short`
  - result: 3 passed.
- `uv run pytest src/aeat/application/modelo/tests/test_import_flow.py src/aeat/application/modelo/tests/test_reconcile.py -q --tb=short`
  - result: 36 passed.

## Notes

No live AEAT read is claimed by this record. The current live blocker remains
Cl@ve completion timeout; this step hardens the local calendar projection once
verified justificante metadata is available.
