---
tags:
  - '#exec'
  - '#live-pull-verification-sweep'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S14'
related:
  - '[[2026-06-12-live-pull-verification-sweep-plan]]'
  - '[[2026-06-12-live-pull-verification-sweep-code-review-audit]]'
---

# W02.P04.S14 / W03.P05.S22 / W04.P07.S29 justificante pull enrolment outcome

## Scope

Hardened the direct live justificante capture orchestrator so `justificante
pull` reports whether the authenticated receipt was enrolled onto a local
filing record as official AEAT filing evidence. The local application filing
axis and the real AEAT filing evidence axis remain distinct: a capture can
persist without stamping when no local filing record exists, but a current
filing record with mismatched taxpayer, modelo, period, year, snapshot state, or
existing AEAT evidence now fails instead of being silently skipped.

## Description

- Add `JustificanteCaptureOutcome` and
  `capture_justificante_snapshot_outcome` to return both the persisted live
  capture snapshot and the stamped local filing record, when one exists.
- Keep the existing `capture_justificante_snapshot` API as a compatibility
  wrapper over the outcome-returning path.
- Change the best-effort stamp helper to skip only the no-current-filing and
  parse-invalid cases; current-record conflicts now propagate to the caller.
- Update `aeat app live justificante pull` to emit
  `filing_evidence_stamped` and, when present, `filing_record_id` in text and
  JSON payloads.
- Add real-behavior tests using the real Modelo 130 justificante PDF fixture
  for stamped outcome reporting, unstamped no-current-filing outcome reporting,
  conflicting existing AEAT evidence refusal, and taxpayer mismatch refusal.

## Outcome

Changed code:

- `src/aeat/application/live/__init__.py`
- `src/aeat/application/live/_justificante.py`
- `src/aeat/application/live/tests/test_justificante_reconcile_from_persisted.py`
- `src/aeat/entrypoints/cli/_app_live_justificante_cli.py`
- `src/aeat/entrypoints/cli/_app_live_payloads.py`

Verification:

- `vaultspec-rag search "live justificante capture filing evidence calendar enrolment pull only" --type code --port 8766 --max-results 12 --timeout 240`
  - result: `http_search_timeout`; exact symbol discovery continued with `rg`.
- `rg -n "capture_justificante_snapshot_outcome|filing_evidence_stamped|filing_record_id|except \(LiveApplicationInputError|except LiveApplicationInputError|tempfile|mkstemp|NamedTemporaryFile|_materialized_capture_pdf|pull-all|pull_all" src/aeat/application/live src/aeat/entrypoints/cli/_app_live_justificante_cli.py src/aeat/entrypoints/cli/_app_live_payloads.py src/aeat/application/modelo`
  - result: no temp-file bridge or new `pull-all` surface in the reviewed justificante/modelo path; existing filed-history conflict catches remain in the filed observation enrollment surface.
- `uv run ruff check src/aeat/application/live/__init__.py src/aeat/application/live/_justificante.py src/aeat/application/live/tests/test_justificante_reconcile_from_persisted.py src/aeat/entrypoints/cli/_app_live_justificante_cli.py src/aeat/entrypoints/cli/_app_live_payloads.py`
  - result: passed.
- `uv run pytest src/aeat/application/live/tests/test_justificante_reconcile_from_persisted.py -q`
  - result: 18 passed.
- `uv run pytest -m "" src/aeat/entrypoints/cli/tests/test_live_justificante_verbs.py src/aeat/entrypoints/cli/tests/test_live_read_subgroups.py -q`
  - result: 27 passed.
- `uv run pytest -m "" src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_filed_pull_cli_help_supports_bulk_options_without_pull_all src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_expedientes_pull_cli_help_supports_bulk_options_without_pull_all src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_command_tree_rejects_pull_all_and_capture_all_aliases -q`
  - result: 3 passed.
- `uv run pytest -m "" src/aeat/entrypoints/cli/tests/test_app_live_filed_rendering.py::test_live_filed_bulk_pull_text_reports_failures_without_pull_all -q`
  - result: 1 passed.
- `uv run pytest -m "" src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_pull_help_locale_keys_do_not_use_capture_all_names -q`
  - result: 1 passed.
- `uv run pytest src/aeat/application/calculations/tests/test_cross_period_clean_state.py src/aeat/application/modelo/tests/test_import_flow.py -q`
  - result: 57 passed.
- `uv run pytest -m "" src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py -q`
  - result: 17 passed.
- `uv run pytest src/aeat/core/tests/test_json_envelope_roundtrip.py src/aeat/core/tests/test_output_rendering.py -q`
  - result: 11 passed.
- `uv run aeat app live justificante pull --help`
  - result: help exposes `pull` with `--modelo`, `--year`, and `--period`; no `pull-all`.
- `uv run aeat app live filed pull --help`
  - result: help exposes bounded single/bulk options under `pull`; no `pull-all`.
- `uv run aeat config profile censo pull --help`
  - result: censo surface is `pull`.
- `uv run aeat app overview calendar --help`
  - result: calendar remains a local projection command and states it never contacts AEAT.
- `uv run aeat config profile status`
  - result: refused because `AEAT_SECRET_PASSPHRASE` is not set and this Codex terminal is non-interactive.
- `uv run aeat config auth status`
  - result: refused for the same non-interactive missing passphrase condition.
- `vaultspec-core vault feature index -f live-pull-verification-sweep`
  - result: passed; regenerated `.vault/index/live-pull-verification-sweep.index.md`.
- `vaultspec-core vault plan check .vault/plan/2026-06-12-live-pull-verification-sweep-plan.md`
  - result: passed.
- `vaultspec-core vault check all --feature live-pull-verification-sweep --no-hints`
  - result: failed on 47 existing structure errors for noncanonical exec filenames
    and one missing-ADR warning; the new S14 exec record was renamed to the
    canonical L4 filename and is not among the remaining structure errors.
- Code review:
  - result: reviewer Hilbert found no blocking findings; audit entry `LPS-027`
    was appended to `2026-06-12-live-pull-verification-sweep-code-review-audit`.

## Notes

This record does not close positive live-auth rows. The operator is ready to
authenticate, but the Codex shell cannot prompt for the secret-store passphrase;
`AEAT_SECRET_PASSPHRASE` must be supplied with a user-chosen value of at least
eight characters before live Modelo 036/censo, filed-history, justificante, and
calendar aggregation pulls can be executed here. The non-production development
password remains deliberately unused for live taxpayer data.
