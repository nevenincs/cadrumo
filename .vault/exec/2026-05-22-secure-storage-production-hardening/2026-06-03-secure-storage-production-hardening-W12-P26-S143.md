---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
modified: '2026-06-03'
step_id: 'S143'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-03-secure-storage-production-hardening-w12-p26-s143-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S143`

Closed `AFR-041` for the Google Drive storage provider.

## Description

- Reviewed `src/aeat/adapters/outbound/storage/_google_drive.py` against the `remote-provider` scanner signal.
- Removed import-time `Settings()` construction for the Drive vault folder name.
- Added explicit `vault_folder_name` constructor wiring and passed the centralized setting from `get_storage_provider`.
- Removed the unused `json` import and `_ = json` suppression pattern.
- Replaced raw upstream exception text in Drive request errors with structured `action` and `status` context.
- Added sanitized debug logging before Drive API boundary exception translation.
- Removed raw upstream exception chaining/context attachment from translated Drive request failures.
- Added `translated_message` keys for Google Drive provider validation, ownership, import, response-shape, not-found, and integrity refusals.
- Updated locale catalogs through `python -m aeat.locales scaffold` and `python -m aeat.locales set`.
- Added no-network real refusal-path coverage for Drive provider constructor and pre-service validation failures.
- Resolved the reviewer medium privacy finding with a request-boundary redaction test proving no raw upstream exception is attached to the typed error.
- Closed `W12.P26.S143` through `vaultspec-core vault plan step check` and aligned the AFR register row to `closed`.

## Outcome

`AFR-041` is closed as `remote-mirror`.

Validation passed:

- `uv run --no-sync pytest -q src/aeat/adapters/outbound/storage/test_google_drive.py src/aeat/adapters/outbound/storage/test_factory.py src/aeat/core/test_external_constants.py -k "google_drive or binary_mime"`
- `uv run --no-sync ruff check src/aeat/adapters/outbound/storage/_google_drive.py src/aeat/adapters/outbound/storage/test_google_drive.py src/aeat/adapters/outbound/storage/_factory.py src/aeat/adapters/outbound/storage/test_factory.py`
- `uv run --no-sync -q python -m aeat.locales audit`
- `rg -n "Settings\(|_Settings\(|PROJECT_ROOT|os\.environ|print\(|typer\.echo|# noqa|pragma|type: ignore|monkeypatch|_Fake|_Stub|skip\(|xfail|import json|_ = json" src/aeat/adapters/outbound/storage/_google_drive.py src/aeat/adapters/outbound/storage/test_google_drive.py src/aeat/adapters/outbound/storage/_factory.py src/aeat/adapters/outbound/storage/test_factory.py`

## Notes

The source scan intentionally returned no matches for direct settings construction, project-root constants, direct environment access, print/echo output, suppression pragmas, monkeypatching, test fakes/stubs, skips, xfails, or the removed `json` suppression pattern.

Two `except Exception` Drive API boundary catches remain in `_google_drive.py`; both log sanitized debug evidence and re-raise typed `OutboundStorageError` subclasses with structured context. They are not swallowing failures and they do not attach raw upstream exceptions to the raised typed error.
