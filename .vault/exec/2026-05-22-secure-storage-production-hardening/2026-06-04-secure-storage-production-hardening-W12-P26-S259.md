---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S259'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s259-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S259`

Closed `AFR-157` for calc-sheets records.

## Description

- Reviewed `src/aeat/application/storage/calc_sheets/_records.py` as the strict record schema shared by engine, offline workbook export, Google apply, and pull reconciliation.
- Constrained `SheetExportMetadata.registry_sha` to lowercase hex so persisted workbook metadata cannot accept arbitrary opaque strings.
- Added a `SheetExportPlan` validator that rejects duplicate writable value/formula cell addresses before any adapter can persist conflicting writes.
- Migrated record validators from bare `ValueError` or raw rendered record errors to `CalcSheetsRecordError` with localized message keys and non-sensitive context.
- Rebased `CalcSheetsRecordError` on the canonical `CoreValidationError` so pydantic validation remains compatible without leaving the AEAT error hierarchy.
- Preserved the canonical `_utc_now` clock alias and UTC-aware export metadata validation.
- Added real pydantic record tests for redacted invalid column letters, typed A1 mismatch errors, typed range errors, and duplicate writable-cell rejection.
- Enrolled record-error translated-message keys through `python -m aeat.locales`.
- Closed `S259` through `vaultspec-core vault plan step check` and aligned the AFR register row.

## Outcome

`AFR-157` is closed as `remote-mirror`. The records module remains non-persistent and frozen/strict, while workbook identity metadata, validation errors, and write-plan consistency are stricter before reaching local workbook or Google Sheets adapters.

Validation passed:

- `uv run --no-sync ruff check src/aeat/application/storage/calc_sheets/_errors.py src/aeat/application/storage/calc_sheets/_records.py src/aeat/application/storage/calc_sheets/test_records_hardening.py src/aeat/test_calc_sheets_error_hierarchy.py`
- `uv run --no-sync pytest -q src/aeat/application/storage/calc_sheets/test_records_hardening.py src/aeat/application/storage/calc_sheets/test_records_evidence.py src/aeat/application/storage/calc_sheets/test_records.py src/aeat/test_calc_sheets_error_hierarchy.py`
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit`

## Notes

Pydantic model validators still surface as `ValidationError`, which is the expected schema-boundary behavior for record construction. The wrapped validation cause is now a `CalcSheetsRecordError` that also derives from the core validation baseclass.
