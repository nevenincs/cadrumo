---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-02'
step_id: 'S431'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-02-secure-storage-production-hardening-W05-P10-S43-review]]'
---

# `secure-storage-production-hardening` `W06.P11.S431`

## Description

- Tracks calc-sheets workbook export proof and quota-aware live Sheet read handling.
- Covers the existing `AEAT 130 1T 2025` workbook under the configured app-owned Drive hierarchy.

## Outcome

Closed.

Evidence:

- Manual read-only Drive connector inspection confirmed `aeat-test-fixtures` -> `aeat-vault` -> `calc-sheets` -> `130-1T-2025` -> `AEAT 130 1T 2025`.
- Earlier bounded reads of `Guía` and `Cálculos` confirmed metadata, formula text, and formatted calculated values.
- Fresh direct Sheets metadata reads on 2026-06-02 hit Google Sheets 429 `ReadRequestsPerMinutePerProject`, so the quota condition is live evidence, not hypothetical.
- Full XLSX export and raw XLSX fetch for `AEAT 130 1T 2025` succeeded through the Drive connector while direct Sheets reads were quota-limited; the extracted workbook content included the Modelo 130 workbook metadata, computed values, procedural rows, tariffs, registry SHA `0370c20383923443`, and export timestamp `2026-05-15T10:47:21.134782+00:00`.
- The shared Google API executor now calls google-api-python-client requests with `num_retries=3`.
- The shared Google API executor now maps HTTP 429 and rate-limit HTTP 403 payloads to `OutboundStorageQuotaError` instead of generic network/permission errors.
- `test_api.py` no longer uses a fake response or import skip for `HttpError`; quota coverage uses real `httplib2.Response` and `googleapiclient.errors.HttpError`.
- Fixed bundled registry validation blockers exposed by the calc-sheets pull test instead of relaxing tests.
- `uv run --no-sync pytest -q src/aeat/adapters/outbound/google/test_calc_sheets_apply.py src/aeat/adapters/outbound/google/test_calc_sheets_pull_typing.py src/aeat/adapters/outbound/google/test_calc_sheets_row_set_headers.py src/aeat/adapters/outbound/google/test_worksheet_export_pull_roundtrip.py src/aeat/domain/calculations/registry/test_modelo_202_registry.py src/aeat/application/calculations/test_relation_prefill_source_mesh.py src/aeat/application/calculations/test_modelo_202_cuota_base_ejercicio_anterior_continuity.py`
  passed with 30 tests.
- `uv run --no-sync pytest -q src/aeat/adapters/outbound/google/test_api.py` passed with 12 tests.
- `uv run --no-sync pytest -q src/aeat/test_calc_sheets_error_hierarchy.py src/aeat/adapters/outbound/storage/test_foundation.py` passed with 22 tests.
- Targeted Ruff over the S431 Python surfaces passed.

Note: repo-native live Drive mirror validation remains blocked by `W06.P11.S430`, not by calc-sheets export or quota handling.
