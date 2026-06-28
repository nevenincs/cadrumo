---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S428'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-02-secure-storage-production-hardening-w05-p10-s43-review-audit]]'
---

# `secure-storage-production-hardening` `W06.P11.S428`

## Description

- Verified the active profile's replacement Google OAuth Desktop client and app-owned Drive root after `W06.P11.S430` restored session readiness.
- Ran repo-native read-only Drive readiness, encrypted mirror dry-run, encrypted mirror push, live Drive provider tests, calc-sheets export, calc-sheets parity verify, calc-sheets pull, and bounded formula/value reads.
- Preserved redacted hierarchy, mirror, and calc-sheets evidence without storing live OAuth client ids, Drive file ids, account emails, spreadsheet ids, or object HMACs.

## Evidence

- `aeat config google status` reports `client_registered=True`, `session_present=True`, and `reauth_required=False` for the replacement Desktop client.
- `aeat config google folder get` reports `configured=True` and the app-owned root folder id.
- `aeat config google sync probe --read-only` reports `provider_kind=google_drive`, `reachable=True`, `writable=False`, `root_folder_present=True`, and `detail=read_only probe; sentinel round-trip skipped`.
- `aeat config google sync push --dry-run` inspected the active bucket and reported 26 secure-object rows across 11 namespaces with zero failures.
- `aeat config google sync push` uploaded 26 ciphertext objects and 11 namespace manifests with `failed_total=0`, `manifest_failed_total=0`, and `manifest_degraded_total=0`.
- Redacted Drive hierarchy inspection found one root child, `aeat-vault`; after mirror and calc-sheets runs, `aeat-vault` contained 14 children: `_probe` with 0 children, `_sync-state` with 11 manifest objects, 11 namespace folders with object counts matching the mirror push, and `calc-sheets` with one child folder.
- `aeat config google sync calc export --modelo 130 --period 1T --year 2025` wrote a Modelo 130 workbook for revision `2019-y-siguientes` with engine `calc-sheets/0.1.0`, registry SHA `da9952e1610f7db6`, 181 value cells, 11 formula cells, 4 protected ranges, and 6 tabs.
- `aeat config google sync calc verify --modelo 130 --period 1T --year 2025` completed with `computed_count=11`, `divergence_count=0`, and verdict `inconclusive` because no AEAT oracle scenario was supplied.
- `aeat config google sync calc pull --modelo 130 --period 1T --year 2025 --spreadsheet-id <exported-workbook-id> --compute` reported `metadata_match=matches`, registry SHA `da9952e1610f7db6`, zero operator edits, and computed 11 outputs including casillas 03, 04, 07, 09, 11, 12, 13, 14, 17, 19, and `saldo-negativo-fin-periodo`.
- Bounded Sheets metadata/range reads against the exported workbook confirmed title `AEAT 130 1T 2025`, tabs `Entradas`, `Cálculos`, `Procedencia`, `Tarifas`, `Detalle`, and `Guía`, `Guía!A1:B20` registry SHA `da9952e1610f7db6`, `Cálculos!A1:H40` formula rows including casilla 03 `=ROUND((Entradas!D2-Entradas!D3),2)` and the downstream formula chain, and `Cálculos!A1:D12` formatted values 0, 0, 0, 0, 0, 0, 100, -100, -100, -100, and 100 for the calculated rows.
- Post-push live provider gate passed: `AEAT_LIVE_TESTS_ENABLED=1 AEAT_LIVE_TESTS_GOOGLE=1 AEAT_STORAGE_PROVIDER_KIND=google_drive AEAT_GOOGLE_DRIVE_ROOT_FOLDER_ID=<app-owned-root-folder-id> pytest -m live_read src/aeat/adapters/outbound/storage/test_google_drive_live.py -q` collected and passed 4 tests.
- 2026-06-03 continuation evidence under `W06.P11.S441` independently rechecked the active profile, read-only probe, Drive hierarchy, empty `_probe` cleanup state, workbook metadata, XLSX export, live Sheets formula read, live Sheets 429 quota response, successful value read after quota reset, and the enabled 4-test live Drive provider gate.

## Status

`W06.P11.S428` is closed.

Drive mutation note: the completed verification uploaded encrypted mirror objects and manifests, created calc-sheets workbook artifacts under the app-owned root, and allowed live provider tests to create and delete `_probe` sentinel/manifest objects. No plaintext secure-object payloads were uploaded.
