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

- Verified the connected Google Drive account can see the existing app fixture hierarchy without write/delete operations.
- Configured the AEAT Google folder id to the parent folder `1ia6jGjO2Dasm8Fn5cYcgrDSSwW5X8MHQ`, preserving the existing `aeat-vault` child folder instead of creating a nested vault.
- Registered the repo-native OAuth desktop client for the active profiles.
- Ran repo-native readiness probes and live test gates.
- Read bounded live Google Sheets ranges for the configured calc-sheets workbook.
- Re-attempted full workbook XLSX export through the Drive connector after the earlier quota failure.

## Evidence

- `aeat config google folder get` reports `configured=True` and `root_folder_id=1ia6jGjO2Dasm8Fn5cYcgrDSSwW5X8MHQ`.
- `aeat config google status` reports `client_registered=True` and `session_present=False`.
- `aeat config google sync probe --read-only` refuses with a typed Google auth failure: no persisted OAuth token for the active profile.
- Disabled live pytest run: `pytest -q -rs -m live_read src/aeat/adapters/outbound/storage/test_google_drive_live.py` collected 4 tests and skipped all 4 because `AEAT_LIVE_TESTS_ENABLED` was not set.
- Enabled live pytest run with Drive env selected collected 4 tests and failed all 4 at provider construction with `OutboundStorageValidationError: no Google OAuth token persisted`.
- Manual Drive connector inspection found parent `aeat-test-fixtures`, existing `aeat-vault`, `calc-sheets`, `130-1T-2025`, and spreadsheet `AEAT 130 1T 2025`.
- Spreadsheet metadata shows tabs `Entradas`, `Cálculos`, `Procedencia`, `Tarifas`, and `Guía`.
- Bounded `Guía!A1:B20` read confirmed Modelo `130`, Revisión `2019-y-siguientes`, Registry SHA `0370c20383923443`, and export timestamp `2026-05-15T10:47:21.134782+00:00`.
- Bounded `Cálculos!A1:H40` formula read confirmed formula cells including casilla 03 `=ROUND((Entradas!D2-Entradas!D3),2)` and downstream derived formulas.
- Bounded `Cálculos!A1:D12` formatted-value read confirmed live calculated values for casillas 03, 04, 07, 09, 11, 12, 13, 14, 17, and 19.
- Fresh bounded range reads for `Guía!A1:B20`, `Cálculos!A1:H40`, and `Cálculos!A1:D12` hit Google Sheets HTTP 429 `ReadRequestsPerMinutePerProject`.
- Fresh full XLSX export through the connector succeeded for spreadsheet `1opH1auOERQNZlAqF5lw3O5ttowwiYRHp0T5V48s79Ck`.
- Raw XLSX fetch through the connector succeeded while direct Sheets reads remained quota-limited, returning extracted workbook content for Modelo 130 metadata, calculated values, procedural rows, tariffs, registry SHA `0370c20383923443`, and export timestamp `2026-05-15T10:47:21.134782+00:00`.
- `W06.P11.S431` remediated quota handling by enabling google-api-python-client retries and mapping HTTP 429 / rate-limit 403 to `OutboundStorageQuotaError`.

Continuation rerun evidence on 2026-06-02:

- Current `aeat config google folder get` reports `configured=True` and root folder id `1ia6jGjO2Dasm8Fn5cYcgrDSSwW5X8MHQ`.
- Current `aeat config google status` reports `client_registered=True`, client id ending `...l62otqf.apps.googleusercontent.com`, and `session_present=False`.
- Disabled repo-native live pytest run `uv run --no-sync pytest -q -rs -m live_read src/aeat/adapters/outbound/storage/test_google_drive_live.py` collected 4 tests and skipped all 4 because `AEAT_LIVE_TESTS_ENABLED` was not `1`.
- Enabled repo-native live pytest run with `AEAT_LIVE_TESTS_ENABLED=1`, `AEAT_LIVE_TESTS_GOOGLE=1`, `AEAT_STORAGE_PROVIDER_KIND=google_drive`, and `AEAT_GOOGLE_DRIVE_ROOT_FOLDER_ID=1ia6jGjO2Dasm8Fn5cYcgrDSSwW5X8MHQ` collected 4 tests and failed all 4 at provider construction with `OutboundStorageValidationError: no Google OAuth token persisted`.
- `aeat config google sync probe --read-only` under the same provider/folder settings emitted JSON error code `REFUSED_CLI_BOUNDARY` with detail `no Google OAuth token persisted`.
- Google Drive connector read-only folder listing confirmed the configured parent contains `aeat-vault` plus the existing smoke doc and smoke sheet.
- Google Drive connector read-only folder listing under `aeat-vault` confirmed `calc-sheets`, `_probe`, and the remote mirror namespace folders including `aeat.google.oauth.client`, `aeat.google.oauth.metadata`, and `aeat.google.oauth.token`.
- Google Sheets connector metadata for spreadsheet `1opH1auOERQNZlAqF5lw3O5ttowwiYRHp0T5V48s79Ck` confirmed title `AEAT 130 1T 2025` and tabs `Entradas`, `Cálculos`, `Procedencia`, `Tarifas`, and `Guía`.
- Google Sheets connector bounded `Guía!A1:B20` read confirmed Modelo `130`, Revisión `2019-y-siguientes`, Registry SHA `0370c20383923443`, and export timestamp `2026-05-15T10:47:21.134782+00:00`.
- Google Sheets connector bounded `Cálculos!A1:H40` formula read confirmed formulas including casilla 03 `=ROUND((Entradas!D2-Entradas!D3),2)` and the downstream 04/07/09/11/12/13/14/17/19 formula chain.
- Google Sheets connector bounded `Cálculos!A1:D12` formatted-value read confirmed live calculated values for casillas 03, 04, 07, 09, 11, 12, 13, 14, 17, and 19.
- `uv run --no-sync ruff check src/aeat/adapters/outbound/storage/test_google_drive_live.py src/aeat/adapters/outbound/google src/aeat/entrypoints/cli/_config/_google.py` passed.

## Status

`W06.P11.S428` remains open.

Repo-native Drive mirror validation is still blocked on `W06.P11.S430`: the folder id and OAuth client exist, but the active profile has no persisted OAuth token. Calc-sheets export and quota handling are closed under `W06.P11.S431`; no Drive files were created, moved, or deleted during connector inspection.
