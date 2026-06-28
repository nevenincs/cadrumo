---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
modified: '2026-06-03'
step_id: 'S133'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-03-secure-storage-production-hardening-w12-p26-s133-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S133`

Closed `AFR-031` for the Google OAuth active-profile binding helper.

## Description

- Reviewed `src/aeat/adapters/outbound/google/_profile_binding.py` against the `active-profile` and `manifest-bucket` scanner signals.
- Classified the helper as manifest-discovery: it resolves the active profile through the central bucket-pointer precedence chain and does not persist OAuth records, construct storage repositories, choose outbound providers, route SQL storage, or read/write local files directly.
- Replaced the hard-coded no-active-profile remediation suggestion with `tr("adapters.google.profile_binding.suggestions.create_profile")`.
- Added locale leaves through `python -m aeat.locales` and focused resolver coverage for the localized suggestion.
- Updated the Google package module allow-list with the new focused test module.
- Closed `W12.P26.S133` through `vaultspec-core vault plan step check`.

## Outcome

`AFR-031` is closed as `manifest-discovery`.

Validation passed:

- `uv run --no-sync pytest -q src/aeat/adapters/outbound/google/test_profile_binding.py src/aeat/adapters/outbound/google/test_package_module_allowlist.py src/aeat/entrypoints/cli/_config/test_google_error_localisation.py`
- `uv run --no-sync ruff check src/aeat/adapters/outbound/google/_profile_binding.py src/aeat/adapters/outbound/google/test_profile_binding.py src/aeat/adapters/outbound/google/test_package_module_allowlist.py src/aeat/entrypoints/cli/_config/test_google_error_localisation.py`
- `uv run --no-sync -q python -m aeat.locales audit`
- `rg -n "SecureObjectRepository|SecureBoundRepository|StorageProvider|GoogleDrive|LocalStorage|write_text\(|read_text\(|open\(|Path\(|storage_path|aeat_database_url|override_settings|load_settings|os\.environ|getenv" src/aeat/adapters/outbound/google/_profile_binding.py`

## Notes

The final source scan intentionally returned no matches. The helper remains a read-only active-profile resolver; the locale change only affects operator remediation text.

Continuation rerun caught that the locale audit claim was false before the locale leaves were present in all four catalogues. `en.yml`, `es.yml`, `ca.yml`, and `hu.yml` now include `adapters.google.profile_binding.suggestions.create_profile`, and `uv run --no-sync -q python -m aeat.locales audit` passes.
