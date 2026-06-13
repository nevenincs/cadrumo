---
tags:
  - '#exec'
  - '#live-pull-verification-sweep'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S11'
related:
  - '[[2026-06-12-live-pull-verification-sweep-plan]]'
  - '[[2026-06-05-calendar-filing-semantics-adr]]'
---

# W02.P04.S11 / W02.P04.S14 / W03.P06.S27 - filed-pull justificante evidence enrollment

## Description

- Re-grounded the gap with `vaultspec-rag search --timeout 900` against calendar filing semantics, AEAT filed history, justificantes, and cross-period filing state.
- Added in-memory justificante metadata enrollment for filed-declaration observations captured by live `filed pull` and `filed pull-sources`.
- Verified each stored filed-declaration `justificante_pdf` artefact before enrollment by checking encrypted-store bytes against byte count and SHA-256, parsing the PDF in memory, and matching modelo, ejercicio, typed `Period`, and authenticated taxpayer identity.
- Saved only matching parsed justificante metadata into `JustificanteRepository`, so downstream Modelo import and cross-period clean-state gates can resolve the same AEAT receipt metadata as the overview calendar.
- Connected matching filed-history justificantes to the current local `ModeloRecord` by stamping `ExternalEvidenceKind.AEAT_LIVE_CAPTURE`, setting `aeat_accepted=True`, and emitting a `MODELO_LIVE_EVIDENCE_STAMPED` bucket event. This keeps the app's local "ready/filed" record distinct from the real-world AEAT-submitted filing while making AEAT-submitted state explicit.
- Preserved existing accepted official justificante evidence instead of overwriting it: same-CSV `AEAT_JUSTIFICANTE_PDF`/`AEAT_LIVE_CAPTURE` evidence is idempotent, while different-CSV accepted evidence is reported as a conflict and left untouched.
- Added filed pull report and JSON payload fields for `justificante_metadata_count`, `justificante_csvs`, `filing_evidence_stamped_count`, `filing_record_ids`, `filing_evidence_conflict_count`, and `filing_evidence_conflict_record_ids` across single, bulk, and source capture modes.
- Fixed adjacent live CLI typed-period drift in `iva-wallet pull-evidence`: `--target-period` is now resolved to `core.Period` before invoking the backend `capture_iva_remote_state` facade.

## Outcome

Filed-declaration pulls now connect the captured AEAT justificante artefact to the shared Modelo/cross-period receipt metadata repository and the current filed `ModeloRecord`, not only to the overview calendar's local filed-observation projection. A live filed pull that captures a matching justificante PDF can now leave encrypted artefact evidence, calculation observations, parsed `JustificanteRepository` metadata, current-modelo external evidence, and an evented audit trail in the same profile bucket.

This remains local/backend proof. It does not close authenticated live rows, because no fresh live AEAT filed pull was run in this shell after the change.

## Verification

- `uv run vaultspec-rag search --timeout 900 "calendar modelo filing justificante enrollment cross period AEAT filing state local ready to file submitted verified censo filed declarations obligations"` returned the calendar filing semantics ADR, prior calendar/live integration research, and live-censo reconciliation evidence.
- `uv run vaultspec-rag search --timeout 900 "Period core.Period filed history ModeloRecord AEAT justificante calendar pull CLI pull-only enrollment obligations census model 036"` returned the prior pull-only live CLI and typed `Period` evidence, the open live 036 reconciliation plan, and the calendar filing semantics research.
- `TMP=Y:\tmp\aeat-pytest TEMP=Y:\tmp\aeat-pytest uv run pytest src/aeat/application/live/tests/test_filed_capture_calculation_history.py -m "integration or not integration" -q` passed with 20 tests.
- `TMP=Y:\tmp\aeat-pytest TEMP=Y:\tmp\aeat-pytest uv run pytest src/aeat/application/live/tests/test_filed_capture_calculation_history.py src/aeat/application/calculations/tests/test_cross_period_clean_state.py src/aeat/application/overview/tests/test_calendar.py src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py -m "integration or not integration" -q` passed with 128 tests.
- `TMP=Y:\tmp\aeat-pytest TEMP=Y:\tmp\aeat-pytest uv run pytest src/aeat/entrypoints/cli/tests/test_registry_cli.py -k "filed or pull_evidence_resolves_target_period" -m "integration or not integration" -q` passed with 12 selected tests.
- `TMP=Y:\tmp\aeat-pytest TEMP=Y:\tmp\aeat-pytest uv run pytest src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_capture_filed_data_cli_requires_live_gate_before_local_writes src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_capture_source_filed_data_requires_live_gate_before_local_writes src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_filed_pull_cli_help_supports_bulk_options_without_pull_all -m "integration or not integration" -q` passed with 3 tests.
- `uv run ruff check src/aeat/application/live/_filed_observation_persistence.py src/aeat/application/live/_filed_data_capture.py src/aeat/application/live/_remote_state_models.py src/aeat/application/live/__init__.py src/aeat/application/live/tests/test_filed_capture_calculation_history.py src/aeat/entrypoints/cli/_app_live.py src/aeat/entrypoints/cli/_app_live_payloads.py src/aeat/application/calculations/tests/test_cross_period_clean_state.py src/aeat/application/overview/tests/test_calendar.py src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py` passed.
- `TMP=Y:\tmp\aeat-pytest TEMP=Y:\tmp\aeat-pytest uv run pytest src/aeat/entrypoints/cli/tests -k "schema or payload" -m "integration or not integration" -q` passed with 274 selected tests.
- A text scan for `tempfile`, `mkstemp`, `NamedTemporaryFile`, `write(body)`, and `parse_justificante(pdf_path)` over the modified filed-enrollment/calendar parser path returned no matches.
- `vaultspec-code-reviewer` reviewed the filed-pull justificante enrollment slice and reported no findings; LPS-009 records the no-findings audit.
- `vaultspec-code-reviewer` then found `LIVE-FILED-HISTORY-001` and `LIVE-FILED-HISTORY-002`; both were remediated and a remediation review reported no blockers.

## Notes

- The first test attempt failed because the default Windows temp volume was full. Reruns used `Y:\tmp\aeat-pytest`.
- The broader `test_live_read_subgroups.py` plus `test_registry_cli.py` run reached 78 passing tests and 2 unrelated watchdog process-list failures caused by Windows command output decoding in the process-list helper. Filed-specific CLI tests passed separately.
- Closing the completed reviewer agent failed with local disk-full error in thread storage after the review result had already been received; no code or vault write depended on that close operation.
- `W02.P04.S11`, `W02.P04.S14`, and `W03.P06.S27` stay open until authenticated live censo, filed declarations, justificantes, expedientes, notifications, and calendar projection are exercised with the operator present.
