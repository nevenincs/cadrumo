---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S379'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# W12.P26.S379 - Close AFR-277 for Google config remote mirror

Scope: close `AFR-277` for `src/aeat/entrypoints/cli/_config/_google.py` with signals
`secure-object, active-profile, plain-file, remote-provider`, target `remote-mirror`,
and owner `W12.P24.S98`.

## Description

- Audited `src/aeat/entrypoints/cli/_config/_google.py` as the CLI transport for
  Google OAuth, Drive folder configuration, calc-sheets export/pull, and secure-object
  remote mirror push.
- Confirmed the plain-file signal is limited to operator-supplied Desktop OAuth client
  JSON, which is parsed, validated as `OAuthClient`, and persisted through the Google
  session store.
- Confirmed active-profile and secure-object signals route through shared Google
  profile binding and session-store helpers, plus the active-bucket secure-object
  repository for remote mirror push.
- Confirmed the remote-provider surface intentionally builds Google Drive providers
  through the outbound storage factory and uploads ciphertext plus namespace manifests,
  never plaintext secure-object material.
- Localized the sync-push `--limit` non-dry-run refusal detail through
  `cli.config.google.detail.sync_push_limit_requires_dry_run`, with locale leaves set
  through `python -m aeat.locales set`.
- Repaired one moved-test path in `src/aeat/adapters/outbound/storage/tests/test_google_drive.py`
  so the AST import-time settings guard reads the production `_google_drive.py` module.
- Closed `W12.P26.S379` through `vaultspec-core vault plan step check` and updated the
  `AFR-277` register status to `closed`.

## Outcome

`AFR-277` is closed as `remote-mirror`. `_config/_google.py` is an intended remote
provider and secure-object mirror surface: it does not create a competing storage
backend, bypass settings, or expose plaintext secure-object data. Live OAuth/Drive
operations remain behind their configured live-test and operator-auth gates.

Validation passed:

- `uv run --no-sync ruff check src/aeat/entrypoints/cli/_config/_google.py src/aeat/entrypoints/cli/_config/_google_payloads.py src/aeat/entrypoints/cli/_config/tests/test_google_error_localisation.py src/aeat/entrypoints/cli/_config/tests/test_google_sync_push.py src/aeat/entrypoints/cli/_config/tests/test_google_sync_calc_pull_flag.py src/aeat/adapters/outbound/google/tests/test_records.py src/aeat/adapters/outbound/google/tests/test_session_store_roundtrip.py src/aeat/adapters/outbound/google/tests/test_profile_binding.py src/aeat/adapters/outbound/google/tests/test_oauth_flow.py src/aeat/adapters/outbound/storage/tests/test_google_drive.py`
- `uv run --no-sync pytest -q src/aeat/entrypoints/cli/_config/tests/test_google_error_localisation.py src/aeat/entrypoints/cli/_config/tests/test_google_sync_push.py src/aeat/entrypoints/cli/_config/tests/test_google_sync_calc_pull_flag.py src/aeat/adapters/outbound/google/tests/test_records.py src/aeat/adapters/outbound/google/tests/test_session_store_roundtrip.py src/aeat/adapters/outbound/google/tests/test_profile_binding.py src/aeat/adapters/outbound/google/tests/test_oauth_flow.py src/aeat/adapters/outbound/storage/tests/test_google_drive.py`
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit`
- `uv run --no-sync vaultspec-rag search "config google sync push secure object repository Drive remote mirror OAuth active profile session store" --type code --port 8766 --max-results 8`

Additional S379 localization hardening validation passed:

- `uv run --no-sync ruff check src/aeat/entrypoints/cli/_config/_google.py src/aeat/entrypoints/cli/_config/tests/test_google_sync_push.py src/aeat/entrypoints/cli/_config/tests/test_google_error_localisation.py`
- `uv run --no-sync pytest -q -m integration src/aeat/entrypoints/cli/_config/tests/test_google_sync_push.py`
- `uv run --no-sync pytest -q -m integration src/aeat/entrypoints/cli/_config/tests/test_google_error_localisation.py`
- `uv run --no-sync -q python -m aeat.locales audit`

Additional Google adapter topology validation passed:

- `uv run --no-sync ruff check src/aeat/adapters/outbound/google/tests/test_calc_sheets_apply.py src/aeat/adapters/outbound/storage/tests/test_google_drive.py src/aeat/entrypoints/cli/_config/_google.py src/aeat/entrypoints/cli/_config/tests/test_google_sync_push.py src/aeat/entrypoints/cli/_config/tests/test_google_error_localisation.py`
- `uv run --no-sync pytest -q src/aeat/adapters/outbound/google/tests src/aeat/adapters/outbound/storage/tests/test_google_drive.py src/aeat/entrypoints/cli/_config/tests/test_google_sync_push.py src/aeat/entrypoints/cli/_config/tests/test_google_error_localisation.py`
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit`

## Notes

The focused pytest run passed with 34 selected tests and 13 deselected live or
marker-gated tests. The broader Google adapter sweep also passed with 160 selected tests
and 13 deselected tests after repairing the moved-test topology for the calc-sheets apply
source guard. No live Google OAuth or Drive mutation test was forced in this offline
closure.
