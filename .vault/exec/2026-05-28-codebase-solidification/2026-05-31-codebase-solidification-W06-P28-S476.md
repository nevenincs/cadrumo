---
step_id: S476
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-31
modified: '2026-05-31'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# codebase-solidification W06.P28 — S476-S485 batch exec record

Steps S476 through S485 were executed in a single commit as they form a coherent A1 exceptions sweep.

## Steps closed

- S476: `CalcSheetsEngineError(AeatError)` in `calc_sheets/_errors.py`; 3 ValueError raises migrated in `_engine.py` (lines 57, 300, 309)
- S477: `CalcSheetsRecordError(AeatError)`; 2 ValueError raises migrated in `_records.py` column-index utilities (lines 83, 94)
- S478: `CalcSheetsParityError(AeatError)`; 1 ValueError raise migrated in `_parity_harness.py` (line 154)
- S479: `_calc_sheets_pull.py:745` column ValueError migrated to `OutboundStorageValidationError`
- S480: 5 constructor ValueError guards in `user_profile/_repository.py` (lines 97, 112, 114, 124, 222) migrated to `BucketValidationError`
- S481: `FinancialProviderConfigError(FinancialProviderError)` introduced; 5 TypeError raises in `financial/providers/_base.py` `__init_subclass__` migrated
- S482: `except Exception` swallow at `sede/_notifications.py:449` narrowed to `(PlaywrightError, OSError)` with documentation comment
- S483: `ValueError` mixin dropped from `BucketValidationError`; Pydantic field validators in `_manifest.py` and `_export_header.py` migrated to raise plain `ValueError`; 3 test files updated to catch `BucketValidationError` directly
- S484: `ValueError` mixin dropped from `GoogleAuthValidationError`; existing test updated to assert `not issubclass`
- S485: Aggregate real-behavior test at `src/aeat/test_w06_p28_exceptions.py` with 11 assertions covering MRO, error code registration, and envelope roundtrip

## New error class registry codes

| Class | Code |
|---|---|
| `CalcSheetsEngineError` | `ERROR_CALC_SHEETS_ENGINE` |
| `CalcSheetsRecordError` | `ERROR_CALC_SHEETS_RECORD` |
| `CalcSheetsParityError` | `ERROR_CALC_SHEETS_PARITY` |
| `FinancialProviderError` | `ERROR_FINANCIAL_PROVIDER` |
| `FinancialProviderConfigError` | `ERROR_FINANCIAL_PROVIDER_CONFIG` |

## MRO migration impact

`BucketValidationError`: 3 caller test files needed updates (`test_cluster_envelopes.py`, `test_keystore_paths.py`, `test_layout.py`, `test_repository.py`). Pydantic field validators in `_manifest.py` and `_export_header.py` raised `BucketValidationError` inside `@field_validator` methods — after MRO removal, these must raise plain `ValueError` so Pydantic catches and converts them. The standalone function raises (in `_keystore_paths.py`, `_layout.py`, `_manifest_io.py`) continue to raise `BucketValidationError` directly.

`GoogleAuthValidationError`: No Pydantic field validator call sites. Only CLI handler raises. Test updated to assert `not issubclass`.

## Locale audit

All 5 new error keys scaffolded and populated with prose translations across ca/en/es/hu. `python -m aeat.locales audit` reports `ok` for all locale files.

## Raises migrated per file

- `_engine.py`: 3 ValueError → CalcSheetsEngineError
- `_records.py`: 2 ValueError → CalcSheetsRecordError
- `_parity_harness.py`: 1 ValueError → CalcSheetsParityError
- `_calc_sheets_pull.py`: 1 ValueError → OutboundStorageValidationError
- `user_profile/_repository.py`: 5 ValueError → BucketValidationError
- `financial/providers/_base.py`: 5 TypeError → FinancialProviderConfigError
- `bucket/_manifest.py`: 4 BucketValidationError → ValueError (Pydantic contract)
- `bucket/_export_header.py`: 4 BucketValidationError → ValueError (Pydantic contract)

## Pytest outcome

68 tests pass across affected modules. 11 new assertions in `test_w06_p28_exceptions.py` all green.

## Collision signal

No authored-file collisions. Pre-existing WIP in other campaign files (`_bindings.py`, wizard files, locale files) was not touched.

## Commit SHA

`f1b5a4b03`
