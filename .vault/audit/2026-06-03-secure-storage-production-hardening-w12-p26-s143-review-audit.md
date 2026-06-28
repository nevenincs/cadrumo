---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
modified: '2026-06-03'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-03-secure-storage-production-hardening-W12-P26-S143]]'
---

# `secure-storage-production-hardening` `W12.P26.S143` Review

## S143-001 | PASS | Google Drive provider no longer constructs settings at import time

The provider previously read `Settings().aeat_google_drive_vault_folder_name` into a module constant. That bypassed the active factory path, made import behavior depend on settings construction, and violated the central settings routing rule.

Resolution: the provider accepts `vault_folder_name` at construction time, falls back to `load_settings()` only when directly constructed without the argument, and the factory passes `settings_resolved.aeat_google_drive_vault_folder_name` explicitly. A source-boundary test asserts `_google_drive.py` does not call `Settings()` or `_Settings()`.

## S143-002 | PASS | Provider refusals are localized and structured

Drive provider validation, import, request, ownership, response-shape, not-found, and integrity failures now carry `translated_message` keys and structured context. Raw upstream exception text is no longer embedded in the operator-facing message, debug log line, exception cause, or exception context for Drive request failures.

Resolution: new locale keys were scaffolded and authored through `python -m aeat.locales`. `python -m aeat.locales audit` passes for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.

## S143-003 | PASS | Exception boundary logs and re-raises typed errors

The provider still has two broad catches at the Google API boundary because the upstream Drive request object can raise heterogeneous third-party exceptions. Those catches now log sanitized debug evidence and re-raise the mapped `OutboundStorageError` subclass with structured context.

Resolution: the broad catches are retained only at the third-party request boundary. No exception is swallowed, and the translated error is raised outside the raw exception context so `__cause__` and `__context__` remain empty.

## S143-004 | PASS | Tests cover real pre-service refusal behavior without fakes

The new Google Drive provider tests instantiate the real provider and exercise constructor and validation refusals that happen before service construction. They also drive the `_execute` request boundary with a plain non-request object to prove the typed error redacts upstream detail and has no raw cause/context. They do not patch dependencies, fake the Drive API, monkeypatch environment variables, skip, or xfail.

Validation:

- `uv run --no-sync pytest -q src/aeat/adapters/outbound/storage/test_google_drive.py src/aeat/adapters/outbound/storage/test_factory.py src/aeat/core/test_external_constants.py -k "google_drive or binary_mime"` passed with 14 selected tests.
- `uv run --no-sync pytest -q src/aeat/adapters/outbound/storage/test_google_drive.py` passed with 8 tests.
- `uv run --no-sync ruff check src/aeat/adapters/outbound/storage/_google_drive.py src/aeat/adapters/outbound/storage/test_google_drive.py src/aeat/adapters/outbound/storage/_factory.py src/aeat/adapters/outbound/storage/test_factory.py` passed.
- `uv run --no-sync -q python -m aeat.locales audit` passed.
- Source scan found no direct `Settings()`, `_Settings()`, `PROJECT_ROOT`, `os.environ`, print/echo output, suppression pragmas, monkeypatching, fakes/stubs, skips, xfails, or `json` suppression pattern in the S143 slice.

Disposition: close `AFR-041` as `remote-mirror`.
