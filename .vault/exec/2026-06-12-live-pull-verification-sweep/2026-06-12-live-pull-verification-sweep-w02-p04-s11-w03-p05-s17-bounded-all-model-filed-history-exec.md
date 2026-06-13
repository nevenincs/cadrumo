---
tags:
  - '#exec'
  - '#live-pull-verification-sweep'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S11'
related:
  - '[[2026-06-12-live-pull-verification-sweep-plan]]'
  - '[[2026-06-12-live-pull-verification-sweep-code-review-audit]]'
  - '[[2026-06-12-live-pull-verification-sweep-live-auth-blocker-audit]]'
---

# W02.P04.S11 / W03.P05.S17 - bounded all-model filed history

## Description

- Investigated the authenticated all-model `app live filed list --from-year 2026 --to-year 2026` timeout observed during the live sweep.
- Added `aeat_live_filed_register_walk_timeout_ms` as a per-model/year filed-register query budget.
- Bounded every filed-register `walk` used by filed list, single filed pull, bulk filed pull, and source filed capture.
- Added `list_filed_data_bulk` so all-model filed listing opens one authenticated register session and returns typed per-model/year failures instead of making the CLI loop over backend calls.
- Kept all-model acquisition under `app live filed list` and `app live filed pull` options; no `pull-all` command is registered.

## Outcome

The all-model filed-history live surface no longer silently hangs the whole CLI when one Modelo/year query stalls. The backend now returns partial results plus `FiledDataCaptureFailureRow` entries for unsupported or timed-out Modelo/year queries.

Authenticated live re-run against the isolated Cl@ve profile completed:

- `app live filed list --from-year 2026 --to-year 2026` returned `row_count=0`, `failed_count=8`, and explicit local-boundary failures for unsupported/no-revision models.
- `app live filed pull --from-year 2026 --to-year 2026` returned `captured_count=0`, `failed_count=8`, `justificante_metadata_count=0`, and `filing_evidence_stamped_count=0`.

No real AEAT filed declaration row was available in the authenticated 2026 account data, so this slice proves bounded all-model filed-history behavior but does not prove a positive justificante pull/enrollment from a live filed row.

## Verification

- `uv run vaultspec-rag search --timeout 900 "live filed history all modelos pull timeout per modelo year justificante calendar enrollment AEAT filed state"` timed out with `code=http_search_timeout`.
- `uv run vaultspec-rag search --timeout 1200 "all-model filed history pull bounded timeout live AEAT register walk justificante enrollment calendar filing evidence"` also timed out with `code=http_search_timeout`; RAG was unavailable for this slice despite high timeouts.
- `uv run ruff check src/aeat/core/_config_timeouts.py src/aeat/application/live/_filed_data.py src/aeat/application/live/_filed_data_capture.py src/aeat/application/live/__init__.py src/aeat/application/live/tests/test_filed_bulk_capture.py src/aeat/entrypoints/cli/_app_live.py` passed.
- `TMP=Y:\tmp\aeat-pytest TEMP=Y:\tmp\aeat-pytest uv run pytest src/aeat/application/live/tests/test_filed_bulk_capture.py src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_filed_pull_cli_help_supports_bulk_options_without_pull_all src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_command_tree_rejects_pull_all_and_capture_all_aliases -m "integration or not integration" -q` passed with 7 tests.
- `TMP=Y:\tmp\aeat-pytest TEMP=Y:\tmp\aeat-pytest uv run pytest src/aeat/application/live/tests/test_filed_bulk_capture.py src/aeat/application/live/tests/test_filed_capture_calculation_history.py src/aeat/application/calculations/tests/test_cross_period_clean_state.py src/aeat/application/overview/tests/test_calendar.py src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py src/aeat/entrypoints/cli/tests/test_registry_cli.py -k "filed or pull_all or pull_evidence_resolves_target_period or calendar" -m "integration or not integration" -q` passed with 117 selected tests and 73 deselected.
- `rg "pull-all|pull_all" src/aeat/entrypoints src/aeat/application src/aeat/locales -n` found only guard assertions in `test_registry_cli.py`.
- `uv run aeat app live filed pull-all --help` failed with `No such command 'pull-all'. Did you mean 'pull'?`.
- Authenticated live `app live filed list --from-year 2026 --to-year 2026` completed with `row_count=0`, `failed_count=8`, and no rows.
- Authenticated live `app live filed pull --from-year 2026 --to-year 2026` completed with `captured_count=0`, `failed_count=8`, no observations, no artefacts, no justificante metadata, and no filing evidence stamps.
- Code review `LPS-011` found no blocking issues.

## Notes

- This record does not close the full `W02.P04.S11` row. Positive live source-pull and justificante enrollment still require an authenticated AEAT account state with at least one returned filed declaration row and receipt artefact.
- The live censo/Modelo 036 blocker remains separate: AEAT G313 still returned no readable censo for this authenticated profile.
