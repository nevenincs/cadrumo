---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-02'
step_id: 'S428'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-02-secure-storage-production-hardening-W05-P10-S43-review]]'
---

# `secure-storage-production-hardening` `W06.P11.S428`

## Description

- Verified the connected Google Drive account can see the existing app fixture hierarchy.
- Confirmed `aeat-vault` already exists under the parent folder `aeat-test-fixtures`.
- Configured the AEAT Google folder id to the parent folder `1ia6jGjO2Dasm8Fn5cYcgrDSSwW5X8MHQ`, not the `aeat-vault` folder itself, so the provider resolves the existing vault instead of creating a nested vault.
- Preserved Drive data: no connector write/delete operations were performed during inspection, and the configured id points at the existing app-owned parent.

## Evidence

- `uv run --no-sync aeat config google folder get` now reports `configured=True` and `root_folder_id=1ia6jGjO2Dasm8Fn5cYcgrDSSwW5X8MHQ`.
- Manual connector inspection found `aeat-vault`, `calc-sheets`, `130-1T-2025`, and spreadsheet `AEAT 130 1T 2025`.
- The workbook exposes tabs `Entradas`, `Cálculos`, `Procedencia`, `Tarifas`, and `Guía`.
- Bounded sheet readback confirmed Guía values Modelo `130`, Revisión `2019-y-siguientes`, and Registry SHA `0370c20383923443`.

Current repo-native status on 2026-06-02:

- `uv run --no-sync aeat config google status` reports `client_registered=False` and `session_present=False`.
- `uv run --no-sync aeat config google folder get` reports `configured=False` and `root_folder_id=<unset>` for the active profile.
- Forced live Drive pytest with `AEAT_LIVE_TESTS_ENABLED=1`, `AEAT_LIVE_TESTS_GOOGLE=1`, `AEAT_STORAGE_PROVIDER_KIND=google_drive`, and `AEAT_GOOGLE_DRIVE_ROOT_FOLDER_ID=1ia6jGjO2Dasm8Fn5cYcgrDSSwW5X8MHQ` collected 4 tests and skipped all 4 because the profile-bound storage runtime has no active bucket session.
- `uv run --no-sync pytest src/aeat/adapters/outbound/google/test_worksheet_export_pull_roundtrip.py -q` passed 2 tests.
- `uv run --no-sync ruff check src/aeat/adapters/outbound/google/test_worksheet_export_pull_roundtrip.py src/aeat/adapters/outbound/storage/test_google_drive_live.py` passed.

## Status

`W06.P11.S428` remains open. Connector inspection proves the expected Drive hierarchy exists, and the local calc-sheets export/pull roundtrip is green, but repo-native live validation is still not complete.

Remaining work:

- Restore or persist the Drive root-folder configuration for the active profile through the repo-native configuration path, or run the live validation with an explicit settings-backed root folder override.
- Register the repo-native Google OAuth desktop client for the active profile, then run `aeat config google login` to create the persisted session.
- Run the Google Drive mirror live tests through the project provider path after the AEAT OAuth/session runtime is ready.
- Complete formula-level calc-sheets export inspection once Google Sheets quota allows bounded reads again.
- Keep the storage provider default on local filesystem unless an operator explicitly opts into Drive for a live validation process.

## Blocker

The authenticated connector proves account access and Drive contents, but it does not satisfy the repo code path. A forced live run with `AEAT_LIVE_TESTS_ENABLED=1`, `AEAT_LIVE_TESTS_GOOGLE=1`, `AEAT_STORAGE_PROVIDER_KIND=google_drive`, `AEAT_GOOGLE_DRIVE_ROOT_FOLDER_ID=1ia6jGjO2Dasm8Fn5cYcgrDSSwW5X8MHQ`, and `pytest -m live_read -rs` collected 4 live Drive tests and skipped all 4 because the project storage runtime reports no active bucket session for profile-bound storage. The production CLI read-only probe reaches the repo credential boundary and refuses because `aeat config google status` reports `client_registered=False` and `session_present=False` for the active profile.
