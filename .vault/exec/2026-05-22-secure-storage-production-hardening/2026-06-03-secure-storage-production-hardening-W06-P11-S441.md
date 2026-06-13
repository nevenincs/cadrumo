---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
modified: '2026-06-03'
step_id: 'S441'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-02-secure-storage-production-hardening-w05-p10-s43-review-audit]]'
---

# `secure-storage-production-hardening` `W06.P11.S441`

## Description

- Record continuation proof after the S428-S431 and S440 remediation chain.
- Re-run live Drive provider validation against the active app-owned root.
- Manually inspect Drive hierarchy and calc-sheets workbook contents through the Google Drive connector.
- Preserve real Google Sheets quota behavior and successful formula/value read evidence.
- Keep the current IVA wallet calculation refactor lint-clean where it blocks the calc-sheets regression gate.

## Outcome

Closed.

Evidence:

- Active profile status reported `client_registered=True`, `session_present=True`, and `reauth_required=False`; the configured root folder matched the app-owned Drive root used by prior S428/S430 closure.
- `aeat config google sync probe --read-only` reported `provider_kind=google_drive`, `reachable=True`, `writable=False`, `root_folder_present=True`, and skipped the sentinel round-trip.
- Read-only Drive connector inspection found the configured root folder, a single `aeat-vault` child, `_sync-state` with 11 mirror manifest binaries, `_probe` empty after live tests, and `calc-sheets/130-1T-2025/AEAT 130 1T 2025`.
- Spreadsheet metadata confirmed tabs `Entradas`, `Cálculos`, `Procedencia`, `Tarifas`, `Detalle`, and `Guía`.
- Drive XLSX export for the live workbook succeeded through the connector.
- A bounded Sheets formula read for `Cálculos!A1:K20` succeeded and showed the real Modelo 130 formula chain.
- A bounded Sheets value read initially hit live HTTP 429 `ReadRequestsPerMinutePerProject`; after the quota window reset, `Cálculos!A1:D12` returned computed values including 100, -100, and `saldo-negativo-fin-periodo` 100.
- `uv run --no-sync pytest -q -m live_read src/aeat/adapters/outbound/storage/test_google_drive_live.py` passed with 4 enabled live tests under the configured Google Drive provider.
- `uv run --no-sync pytest -q src/aeat/adapters/outbound/storage/test_mirror_manifest.py src/aeat/adapters/outbound/storage/test_foundation.py src/aeat/entrypoints/cli/_config/test_google_sync_push.py src/aeat/adapters/outbound/google/test_api.py` passed with 46 tests.
- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/crypto/test_encrypted_columns.py src/aeat/adapters/persistence/storage/sql/test_secure_objects.py src/aeat/adapters/persistence/storage/sql/test_archive_bundle_roundtrip.py` passed with 65 tests and 3 pre-existing SQLAlchemy datetime-adapter warnings.
- `uv run --no-sync pytest -q src/aeat/adapters/outbound/google/test_calc_sheets_apply.py src/aeat/adapters/outbound/google/test_calc_sheets_pull_typing.py src/aeat/adapters/outbound/google/test_calc_sheets_row_set_headers.py src/aeat/adapters/outbound/google/test_worksheet_export_pull_roundtrip.py src/aeat/domain/calculations/registry/test_modelo_202_registry.py src/aeat/application/calculations/test_relation_prefill_source_mesh.py src/aeat/application/calculations/test_modelo_202_cuota_base_ejercicio_anterior_continuity.py src/aeat/application/calculations/test_iva_wallet_reconciliation.py` passed with 49 tests.
- Targeted Ruff over the secure-storage, Google API, secure-object ancestry, and current IVA wallet calculation refactor surfaces passed.
- `uv run --no-sync pytest -q src/aeat/application/calculations/test_iva_wallet_reconciliation.py` passed with 19 tests with the current docstring-complete IVA wallet calculation refactor.

## Notes

The Drive connector inspection was read-only. The repo-native live provider gate created and deleted its own `_probe` sentinel objects under the app-owned root; the `_probe` folder was empty after the run. Existing Drive data outside the configured app-owned root was not modified.
