---
tags:
  - '#exec'
  - '#live-pull-verification-sweep'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S14'
related:
  - '[[2026-06-12-live-pull-verification-sweep-plan]]'
  - '[[2026-06-05-live-censo-calendar-reconciliation-plan]]'
  - '[[2026-06-05-calendar-filing-semantics-adr]]'
---

# W02.P04.S14 / W03.P06.S27 - parsed filed-declaration justificante verification

## Description

- Re-grounded filed-declaration justificante verification with `vaultspec-rag search --timeout 900`.
- Tightened the overview CLI storage boundary so a filed-declaration `justificante_pdf` artefact is calendar-verified only after:
  - encrypted artefact bytes load successfully,
  - byte count and SHA-256 match the manifest,
  - the bytes parse as a justificante PDF in memory, without materialising decrypted bytes to a plaintext temp file,
  - parsed modelo, ejercicio, period, and taxpayer identity match the filed-declaration observation.
- Kept unparsable or mismatched justificante artefacts as `submitted_observed` only, never `justificante_verified`.
- Deduplicated observed-only filed-declaration rows after demotion so the calendar does not show duplicate evidence rows for the same period.
- Added a `parse_justificante_bytes` adapter entry point so secure-storage callers can validate justificantes without writing decrypted evidence outside secure storage.

## Outcome

The calendar no longer treats stored bytes alone as justificante verification. A stored filed-declaration artefact must now be an actual matching justificante before it can satisfy the calendar's verified AEAT filing state. This aligns the overview calendar with the Modelo/cross-period invariant that real-world filing evidence is distinct from local readiness and must be reconciled against AEAT filing state.

This record remains local/backend proof. It does not close the authenticated live pull rows, because no live AEAT justificante pull was completed in this shell.

## Verification

- `uv run vaultspec-rag search --timeout 900 "filed declaration observation justificante pdf parse calendar verified storage ref tax identity modelo period"` returned the prior calendar filing semantics audit/ADR and W05.P05.S22 store-verification record.
- `uv run pytest src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py src/aeat/application/overview/tests/test_calendar.py -m "integration or not integration" -q` passed with 78 tests before the secure-storage review remediation.
- `uv run pytest src/aeat/adapters/inbound/justificante/tests/test_parser.py src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py src/aeat/application/overview/tests/test_calendar.py -m "integration or not integration" -q` passed with 159 tests after adding in-memory justificante parsing.
- `uv run ruff check src/aeat/entrypoints/cli/_overview.py src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py src/aeat/application/overview/_calendar.py src/aeat/application/overview/tests/test_calendar.py` passed.
- `uv run pytest src/aeat/application/live/tests/test_justificante_reconcile_from_persisted.py src/aeat/application/live/tests/test_expedientes.py src/aeat/application/overview/tests/test_calendar.py src/aeat/application/calculations/tests/test_cross_period_clean_state.py src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py -m "integration or not integration" -q` passed with 134 tests.
- `uv run pytest src/aeat/adapters/inbound/justificante/tests/test_parser.py src/aeat/application/live/tests/test_justificante_reconcile_from_persisted.py src/aeat/application/live/tests/test_expedientes.py src/aeat/application/overview/tests/test_calendar.py src/aeat/application/calculations/tests/test_cross_period_clean_state.py src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py -m "integration or not integration" -q` passed with 215 tests after the parser remediation.
- `uv run pytest src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_filed_pull_cli_help_supports_bulk_options_without_pull_all src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_expedientes_pull_cli_help_supports_bulk_options_without_pull_all src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_command_tree_rejects_pull_all_and_capture_all_aliases -m "integration or not integration" -q` passed with 3 tests.
- `rg "pull-all" src/aeat/entrypoints/cli -n` returned only registry tests asserting the alias is absent.
- LPS-007 code review finding identified the initial temp-file bridge as a secure-storage violation; LPS-008 records the in-memory parser remediation and focused gates.

## Open Work

`W02.P04.S14` and `W03.P06.S27` stay open until the fresh-profile authenticated live sweep pulls censo, filed declarations, expedientes, notifications, justificantes, and calendar projection with the operator present.
