---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-W12-P26-S259]]'
---

# `secure-storage-production-hardening` `W12.P26.S259` Review

## S259-001 | MEDIUM | Workbook registry hash accepted arbitrary strings

`SheetExportMetadata.registry_sha` was length-bounded but not shape-constrained. The engine emits lowercase SHA-derived hex, and pull/apply reconciliation relies on this identity being stable. The metadata field now accepts only lowercase hex with the existing 8-64 character bounds.

## S259-002 | HIGH | Export plans allowed duplicate writable cell addresses

`SheetExportPlan` could contain multiple value/formula cells targeting the same tab/row/column. That would leave write ordering to adapter implementation details and could persist contradictory workbook state. The plan model now rejects duplicate writable addresses during pydantic validation.

## S259-003 | PASS | Record boundary remains strict and non-persistent

All records continue to use the shared strict frozen model config. The module performs no storage, remote API, logging, credential handling, or environment access. `_utc_now` remains the canonical core clock alias and `SheetExportMetadata.exported_at` remains UTC-aware validated.

## S259-004 | PASS | Validation

- `uv run --no-sync ruff check src/aeat/application/storage/calc_sheets/_records.py src/aeat/application/storage/calc_sheets/test_records_hardening.py src/aeat/application/storage/calc_sheets/test_records.py src/aeat/application/storage/calc_sheets/test_records_evidence.py` passed.
- `uv run --no-sync pytest -q src/aeat/application/storage/calc_sheets/test_records_hardening.py src/aeat/application/storage/calc_sheets/test_records.py src/aeat/application/storage/calc_sheets/test_records_evidence.py src/aeat/application/storage/calc_sheets/test_modelo_export_parity.py` passed with 31 tests.
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit` passed.

Disposition: close `AFR-157` as `remote-mirror` with workbook metadata shape and write-plan collision validation hardened.
