---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-W12-P26-S259]]'
---

# `secure-storage-production-hardening` `W12.P26.S259` Review

## S259-001 | MEDIUM | Workbook registry hash accepted arbitrary strings

`SheetExportMetadata.registry_sha` was length-bounded but not shape-constrained. The engine emits lowercase SHA-derived hex, and pull/apply reconciliation relies on this identity being stable. The metadata field now accepts only lowercase hex with the existing 8-64 character bounds.

## S259-002 | HIGH | Export plans allowed duplicate writable cell addresses

`SheetExportPlan` could contain multiple value/formula cells targeting the same tab/row/column. That would leave write ordering to adapter implementation details and could persist contradictory workbook state. The plan model now rejects duplicate writable addresses during pydantic validation.

## S259-003 | MEDIUM | Record validators used bare errors and raw rendered invalid values

Several pydantic validators raised bare `ValueError`, and invalid column letters were rendered directly into the `CalcSheetsRecordError` message. Record construction failures can cross user-facing CLI and adapter boundaries, so validators now raise `CalcSheetsRecordError` with translated-message keys and non-sensitive context. `CalcSheetsRecordError` now derives from `CoreValidationError`, preserving pydantic compatibility and the AEAT error hierarchy.

## S259-004 | PASS | Record boundary remains strict and non-persistent

All records continue to use the shared strict frozen model config. The module performs no storage, remote API, logging, credential handling, or environment access. `_utc_now` remains the canonical core clock alias and `SheetExportMetadata.exported_at` remains UTC-aware validated.

## S259-005 | PASS | Validation

- `uv run --no-sync ruff check src/aeat/application/storage/calc_sheets/_errors.py src/aeat/application/storage/calc_sheets/_records.py src/aeat/application/storage/calc_sheets/test_records_hardening.py src/aeat/test_calc_sheets_error_hierarchy.py` passed.
- `uv run --no-sync pytest -q src/aeat/application/storage/calc_sheets/test_records_hardening.py src/aeat/application/storage/calc_sheets/test_records_evidence.py src/aeat/application/storage/calc_sheets/test_records.py src/aeat/test_calc_sheets_error_hierarchy.py` passed with 21 tests.
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit` passed.

Disposition: close `AFR-157` as `remote-mirror` with workbook metadata shape, typed validation errors, and write-plan collision validation hardened.
