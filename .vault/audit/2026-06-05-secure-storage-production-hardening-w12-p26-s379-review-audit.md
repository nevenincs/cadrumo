---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-05-secure-storage-production-hardening-W12-P26-S379]]'
---

# `secure-storage-production-hardening` `W12.P26.S379` Review

## S379-001 | PASS | Google config is an intentional remote mirror surface

`src/aeat/entrypoints/cli/_config/_google.py` owns operator-facing Google OAuth, Drive
folder configuration, sync probe, sync push, and calc-sheets export/pull transport. The
remote-provider signal is therefore expected and closes as `remote-mirror`, not as an
accidental runtime-default repository.

## S379-002 | PASS | Secure-object mirror uploads ciphertext only

`google_sync_push` obtains the active-bucket `SecureObjectRepository`, iterates raw
records, computes per-object HMAC names and content hashes, uploads the encrypted
payload bytes through the configured Google Drive provider, and writes namespace
manifests. It does not decrypt records or upload plaintext secure-object contents.

## S379-003 | PASS | Active-profile and settings access use shared authorities

Google commands resolve active profile state through the outbound Google profile
binding helper and load settings through the centralized settings API. The Drive
provider is constructed through the outbound storage factory; `_config/_google.py` does
not read naked environment variables or create a competing backend configuration path.

## S379-004 | PASS | OAuth client JSON is a validated operator input

The plain-file path is the explicit `--client-json` Desktop OAuth client input. The
file is read once, parsed as JSON, rejected unless it has the Cloud Console
`installed` envelope, and narrowed to the strict `OAuthClient` model before persistence.

## S379-005 | FIXED | Google Drive provider AST guard follows moved test topology

`src/aeat/adapters/outbound/storage/tests/test_google_drive.py` now reads the production
`_google_drive.py` module from the parent package directory. The assertion still checks
for import-time `Settings` construction; only the path was corrected after the test
topology move.

## S379-006 | FIXED | Sync push limit refusal detail is localized

The `--limit` guard for non-dry-run Google sync push now attaches
`cli.config.google.detail.sync_push_limit_requires_dry_run` to the
`OutboundStorageValidationError`, so `_google_refusal()` exposes a translated operator
detail instead of leaking an English-only implementation message. Locale leaves were
added through `python -m aeat.locales set`, and the regression test asserts the
projected refusal detail through `tr()`.

## S379-007 | PASS | Validation

- `uv run --no-sync ruff check src/aeat/entrypoints/cli/_config/_google.py src/aeat/entrypoints/cli/_config/_google_payloads.py src/aeat/entrypoints/cli/_config/tests/test_google_error_localisation.py src/aeat/entrypoints/cli/_config/tests/test_google_sync_push.py src/aeat/entrypoints/cli/_config/tests/test_google_sync_calc_pull_flag.py src/aeat/adapters/outbound/google/tests/test_records.py src/aeat/adapters/outbound/google/tests/test_session_store_roundtrip.py src/aeat/adapters/outbound/google/tests/test_profile_binding.py src/aeat/adapters/outbound/google/tests/test_oauth_flow.py src/aeat/adapters/outbound/storage/tests/test_google_drive.py` passed.
- `uv run --no-sync pytest -q src/aeat/entrypoints/cli/_config/tests/test_google_error_localisation.py src/aeat/entrypoints/cli/_config/tests/test_google_sync_push.py src/aeat/entrypoints/cli/_config/tests/test_google_sync_calc_pull_flag.py src/aeat/adapters/outbound/google/tests/test_records.py src/aeat/adapters/outbound/google/tests/test_session_store_roundtrip.py src/aeat/adapters/outbound/google/tests/test_profile_binding.py src/aeat/adapters/outbound/google/tests/test_oauth_flow.py src/aeat/adapters/outbound/storage/tests/test_google_drive.py` passed with 34 selected tests and 13 deselected tests.
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit` passed.
- `uv run --no-sync vaultspec-rag search "config google sync push secure object repository Drive remote mirror OAuth active profile session store" --type code --port 8766 --max-results 8` returned CLI payload, sync push, session-store, and active-profile binding evidence.
- `uv run --no-sync ruff check src/aeat/entrypoints/cli/_config/_google.py src/aeat/entrypoints/cli/_config/tests/test_google_sync_push.py src/aeat/entrypoints/cli/_config/tests/test_google_error_localisation.py` passed after the localized refusal change.
- `uv run --no-sync pytest -q -m integration src/aeat/entrypoints/cli/_config/tests/test_google_sync_push.py src/aeat/entrypoints/cli/_config/tests/test_google_error_localisation.py` passed after the localized refusal change.
- `uv run --no-sync -q python -m aeat.locales audit` passed after adding the locale leaves through the canonical CLI.

## S379-008 | FIXED | Broader Google adapter test topology follows moved package layout

The exact S379 validation command passed, and the repaired Google Drive provider guard now
reads the production `_google_drive.py` module from the parent package. A broader Google
adapter sweep found the same moved-test topology issue in `test_calc_sheets_apply.py`,
where `_APPLY_PY` resolved `_calc_sheets_apply.py` under the `tests` directory instead of
the parent package. The calc-sheets source guard now reads the production module from the
parent package while preserving the existing rationale-marker assertions.

Follow-up validation passed:

- `uv run --no-sync ruff check src/aeat/adapters/outbound/google/tests/test_calc_sheets_apply.py src/aeat/adapters/outbound/storage/tests/test_google_drive.py src/aeat/entrypoints/cli/_config/_google.py src/aeat/entrypoints/cli/_config/tests/test_google_sync_push.py src/aeat/entrypoints/cli/_config/tests/test_google_error_localisation.py`
- `uv run --no-sync pytest -q src/aeat/adapters/outbound/google/tests src/aeat/adapters/outbound/storage/tests/test_google_drive.py src/aeat/entrypoints/cli/_config/tests/test_google_sync_push.py src/aeat/entrypoints/cli/_config/tests/test_google_error_localisation.py` passed with 160 selected tests and 13 deselected tests.
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit`

Reviewer note: no critical, high, medium, or low remote-mirror findings remain for the
S379 slice.

Disposition: close `AFR-277` as `remote-mirror`.
