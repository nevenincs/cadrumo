---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
modified: '2026-06-03'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-03-secure-storage-production-hardening-W12-P26-S142]]'
---

# `secure-storage-production-hardening` `W12.P26.S142` Review

## S142-001 | PASS | Factory concrete backend imports are branch-local

The factory no longer imports `LocalFileSystemProvider` or `GoogleDriveProvider` at module import time. The public storage package can expose `get_storage_provider` without also loading the concrete local and Drive backends. This keeps the public API aligned with the Google OAuth ADR mitigation that heavy Drive dependencies are loaded only when the Drive provider branch is selected.

Resolution: concrete backend imports are now inside the `ProviderKind.LOCAL_FILESYSTEM` and `ProviderKind.GOOGLE_DRIVE` branches. A source-level import-boundary test asserts there are no top-level concrete backend imports in the factory module.

## S142-002 | PASS | Provider factory refusals are localized and structured

The provider-kind parser and Google Drive setup refusals now carry `translated_message` keys plus structured context and suggestions. The blank-kind, unknown-kind, Google client, Google token, google-auth import, missing Drive root, and unreachable unhandled-kind branches all have locale entries in `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.

Resolution: locale keys were scaffolded and authored through the canonical `python -m aeat.locales` CLI. Targeted tests assert the blank, unknown, missing-root, missing-client, and missing-token refusals resolve through typed `translated_message` keys and structured context.

## S142-003 | PASS | Active-profile local provider root is enforced by real runtime setup

The local-provider factory branch resolves the active profile and derives its root with `bucket_paths(settings.aeat_local_storage_root, profile).blobs_dir`. The new test provisions a real isolated runtime profile, obtains the provider through `get_storage_provider`, writes and reads an object, and asserts the backend object path lives under the active profile blob root.

## S142-004 | PASS | Reviewer medium test-completeness finding resolved

The independent review found no critical or high issues, but flagged medium test incompleteness for the Drive branch. The test suite now covers the real missing-client and missing-token branches by provisioning an isolated runtime profile and using the real Google secure session store. The google-auth dependency import failure branch is left as localized typed code rather than simulated with monkeypatching or dependency shadowing.

Validation:

- `uv run --no-sync pytest -q src/aeat/adapters/outbound/storage/test_factory.py src/aeat/adapters/outbound/storage/test_foundation.py -k "factory or public_surface"` passed with 8 selected tests.
- `uv run --no-sync pytest -q src/aeat/adapters/outbound/storage/test_factory.py` passed with 7 tests.
- `uv run --no-sync ruff check src/aeat/adapters/outbound/storage/_factory.py src/aeat/adapters/outbound/storage/test_factory.py` passed.
- `uv run --no-sync -q python -m aeat.locales audit` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.
- Source scan found no direct `Settings()`, `PROJECT_ROOT`, `os.environ`, print/echo output, `# noqa`, pragma, `type: ignore`, broad exception catches, monkeypatching, fakes/stubs, skips, or xfails in the S142 files.

Disposition: close `AFR-040` as `remote-mirror`.
