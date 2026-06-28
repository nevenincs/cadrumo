---
tags:
  - '#exec'
  - '#live-pull-verification-sweep'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S14'
related:
  - '[[2026-06-12-live-pull-verification-sweep-plan]]'
  - '[[2026-06-12-live-pull-verification-sweep-w03-p06-s27-w04-p07-s29-modelo-record-calendar-events-exec]]'
---

# W02.P04.S14 / W03.P05.S22 / W03.P06.S27 / W04.P07.S29 secure-bytes justificante reconcile

## Scope

Hardened live justificante capture reconciliation so a persisted authenticated
receipt can be parsed and reconciled from secure-storage bytes without writing
decrypted PDF bytes to a temp file or plaintext path. Kept the local operator
`reconcile file --file` path file-backed, while the live-capture path records a
secure object reference in reconciliation history.

## Description

- Remove temp-file materialisation from live justificante parsing and
  reconciliation.
- Add a bytes-backed Modelo reconciliation command for secure-storage callers.
- Share the parsed-justificante comparison and bucket-event emission between
  file-backed and bytes-backed reconciliation.
- Record live-capture reconciliation history with a `secure-object://` source
  reference instead of a filesystem path.
- Keep direct live-capture filing evidence stamping gated on active snapshot
  state, current filing record, parsed modelo/year/typed-period/taxpayer
  identity, and existing AEAT evidence conflicts.
- Update persisted live justificante tests to assert secure references, no temp
  path leakage, idempotent same-CSV evidence, conflict refusal, taxpayer
  refusal, period refusal, year refusal, and non-active snapshot refusal.
- Align the overview calendar local-filing-evidence refusal locale copy through
  the locale CLI so corrupt persisted AEAT filing evidence reports a fail-closed
  refusal instead of row-level missing evidence.

## Outcome

Changed code:

- `src/aeat/application/modelo/_reconcile.py`
- `src/aeat/application/modelo/__init__.py`
- `src/aeat/application/live/_justificante.py`
- `src/aeat/application/live/tests/test_justificante_reconcile_from_persisted.py`
- `src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py`
- `src/aeat/locales/en.yml`
- `src/aeat/locales/es.yml`
- `src/aeat/locales/ca.yml`
- `src/aeat/locales/hu.yml`

Verification:

- `vaultspec-rag search "live justificante receipt persisted filing evidence secure storage" --type code --port 8766 --max-results 12 --timeout 180`
  - result: `http_search_timeout`; exact symbol discovery continued with `rg`.
- `vaultspec-rag search "Modelo filing calendar AEAT justificante verified event" --type code --port 8766 --max-results 12 --timeout 180`
  - result: `http_search_timeout`; exact symbol discovery continued with `rg`.
- `vaultspec-rag search "pull only live CLI filed declaration no pull all" --type code --port 8766 --max-results 12 --timeout 180`
  - result: `http_search_timeout`; exact symbol discovery continued with `rg`.
- `vaultspec-rag search "live censo Modelo 036 obligations calendar reconciliation" --type code --port 8766 --max-results 12 --timeout 180`
  - result: `http_search_timeout`; exact symbol discovery continued with `rg`.
- `uv run ruff check src/aeat/application/modelo/_reconcile.py src/aeat/application/modelo/__init__.py src/aeat/application/live/_justificante.py src/aeat/application/live/tests/test_justificante_reconcile_from_persisted.py src/aeat/entrypoints/cli/_overview.py src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py`
  - result: passed.
- `uv run pytest src/aeat/application/live/tests/test_justificante_reconcile_from_persisted.py -q`
  - result: 14 passed.
- `uv run pytest src/aeat/application/modelo/tests/test_reconcile.py src/aeat/application/modelo/tests/test_reconciliation_history.py -q`
  - result: 12 passed.
- `uv run pytest src/aeat/application/overview/tests/test_calendar.py src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py -q`
  - result: overview unit suite passed; CLI suite deselected under default `-m unit`.
- `uv run pytest -m "" src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py -q`
  - result: 17 passed after locale-copy alignment.
- `uv run pytest src/aeat/application/calculations/tests/test_cross_period_clean_state.py -q`
  - result: 31 passed.
- `uv run pytest src/aeat/application/modelo/tests/test_import_flow.py -q`
  - result: 26 passed.
- `uv run pytest -m "" src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_filed_pull_cli_help_supports_bulk_options_without_pull_all src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_expedientes_pull_cli_help_supports_bulk_options_without_pull_all src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_command_tree_rejects_pull_all_and_capture_all_aliases src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_filed_bulk_pull_text_reports_failures_without_pull_all -q`
  - result: 4 passed.
- `uv run pytest -m "" src/aeat/entrypoints/cli/tests/test_live_read_subgroups.py -q`
  - result: 25 passed.
- `uv run python -m aeat.locales scaffold --check`
  - result: failed on pre-existing unrelated locale drift: six missing
    `application.bucket_maintenance.errors.*` keys and two extra
    `cli.overview.warning.*` keys in every locale.
- `uv run aeat app live --help`, `uv run aeat config profile censo --help`,
  `uv run aeat app live filed --help`, and `uv run aeat app live justificante --help`
  - result: live reads expose `pull`, `list`, `view`, and `pull-sources`
    surfaces; no `pull-all` surface was accepted in the focused registry gates.
- `AEAT_SECRET_PASSPHRASE=horatio uv run aeat config auth status --format json`
  - result: refused because `horatio` is shorter than the 8-character
    secret-store policy minimum.
- Read `Settings.aeat_dev_test_database_password`
  - result: value is the documented non-production constant
    `aeat-dev-test-database-password`; not used for live taxpayer data because
    `env/.env.example` explicitly says not to use it for operator profiles or
    live taxpayer data.

Code review:

- Reviewer Gauss appended `LPS-026 | INFO | No blocking review findings for
  live justificante reconcile and calendar fail-closed sweep` to
  `2026-06-12-live-pull-verification-sweep-code-review-audit`.

## Notes

This record does not close the authenticated live acceptance rows. Positive
Modelo 036/censo, filed-history, justificante, and calendar projection pulls
still require an operator-provided compliant secret-store passphrase and a live
AEAT authentication session. The supplied `horatio` passphrase could not unlock
or create profile storage because it violates the minimum length policy, and
the published development password is intentionally non-production.
