---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S385'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# W12.P26.S385 - Close AFR-283 for overview CLI manifest discovery

Scope: close `AFR-283` for `src/aeat/entrypoints/cli/_overview.py` with signals
`active-profile, manifest-bucket`, target `manifest-discovery`, and owner
`W12.P22.S90`.

## Description

- Audited `src/aeat/entrypoints/cli/_overview.py` as the read-only overview CLI surface
  for status, calendar, agenda, backlog, and explain commands.
- Confirmed active-profile access uses the shared CLI `_state()` helper and
  `resolve_active_bucket_id()` refusal path instead of opening storage without an
  active profile.
- Confirmed the all-profiles calendar path uses `list_profile_buckets()` as manifest
  discovery, filters active manifests, then reads encrypted profile records inside
  `profile_storage_session(bucket_id)`.
- Confirmed local live snapshot calendar enrichment reads through bucket-aware
  `ExpedientesService` and `NotificationsService` calls and logs unreadable local
  snapshots at warning with exception info rather than silently swallowing failures.
- Repaired the period-scoped `overview status --period` no-active-profile path so it
  uses the shared `_no_active_profile_refusal()` boundary instead of Click's
  bad-parameter wrapper.
- Added the missing cross-lane `cli.ledger.errors.invalid_category` locale leaves through
  `python -m aeat.locales set` so the required locale audit passes against the current
  shared worktree.
- Closed `W12.P26.S385` through `vaultspec-core vault plan step check` and updated the
  `AFR-283` register status to `closed`.

## Outcome

`AFR-283` is closed as `manifest-discovery`. `_overview.py` is a local, read-only CLI
consumer of active-profile state and manifest inventory. It does not create a competing
secure-storage backend and does not mutate profile, filing, or live-read state.

Validation passed:

- `uv run --no-sync ruff check src/aeat/entrypoints/cli/_overview.py src/aeat/entrypoints/cli/_overview_payloads.py src/aeat/entrypoints/cli/_overview_rendering.py src/aeat/entrypoints/cli/tests/test_overview.py src/aeat/entrypoints/cli/tests/test_overview_verbs.py src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py src/aeat/entrypoints/cli/tests/test_overview_agenda_verb.py src/aeat/entrypoints/cli/tests/test_overview_backlog_verb.py src/aeat/entrypoints/cli/tests/test_overview_explain_verb.py`
- `uv run --no-sync pytest -q -m integration src/aeat/entrypoints/cli/tests/test_overview.py src/aeat/entrypoints/cli/tests/test_overview_verbs.py src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py src/aeat/entrypoints/cli/tests/test_overview_agenda_verb.py src/aeat/entrypoints/cli/tests/test_overview_backlog_verb.py src/aeat/entrypoints/cli/tests/test_overview_explain_verb.py`
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit`
- `uv run --no-sync ruff check src/aeat/entrypoints/cli/_overview.py src/aeat/entrypoints/cli/tests/test_cold_start_no_profile.py src/aeat/entrypoints/cli/tests/test_overview.py src/aeat/entrypoints/cli/tests/test_overview_verbs.py src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py src/aeat/entrypoints/cli/tests/test_overview_agenda_verb.py src/aeat/entrypoints/cli/tests/test_overview_backlog_verb.py src/aeat/entrypoints/cli/tests/test_overview_explain_verb.py`
- `uv run --no-sync pytest -q -m integration src/aeat/entrypoints/cli/tests/test_cold_start_no_profile.py src/aeat/entrypoints/cli/tests/test_overview.py src/aeat/entrypoints/cli/tests/test_overview_verbs.py src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py src/aeat/entrypoints/cli/tests/test_overview_agenda_verb.py src/aeat/entrypoints/cli/tests/test_overview_backlog_verb.py src/aeat/entrypoints/cli/tests/test_overview_explain_verb.py`
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit`

## Notes

The non-marker overview pytest command selected zero tests because the suite is
integration-marker gated. The explicit `-m integration` command passed with 38 tests
before review and 48 tests after adding the cold-start overview-period regression.

`uv run --no-sync pytest -q -m integration src/aeat/entrypoints/cli/tests/test_backend_boundary.py`
failed outside the S385 overview slice on existing ledger/modelo/test-topology findings:
ledger review help vocabulary, modelo work resume `NameError`, two retired moved-test path
guards, and existing skip/xfail/stub language detections. Those failures were not caused by
`_overview.py` and are tracked as residual backlog rather than hidden.

`vaultspec-rag search "entrypoints cli overview active profile manifest bucket list_profile_buckets profile_storage_session runtime" --type code --port 8766 --max-results 8` returned relevant code evidence but timed out after printing results; a shorter follow-up search completed and returned `list_profile_buckets`, profile manifest scanning, and profile repository list evidence.
