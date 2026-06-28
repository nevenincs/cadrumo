---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S260'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s260-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S260`

Closed `AFR-158` for the calc-sheets formula translator.

## Description

- Reviewed `src/aeat/application/storage/calc_sheets/_translator.py` as the formula compiler used before local workbook and Google Sheets export.
- Centralized `TranslationError` construction so legacy raise sites cannot render raw formula ops, parameter ids, or layout identifiers through `str(error)`.
- Added a translated-message key and bounded context for translator failures while preserving the registered `TranslationError` public type.
- Added real registry-backed translator hardening tests for unsupported ops and missing parameter anchors.
- Enrolled translator-error locale strings through `python -m aeat.locales`.
- Closed `S260` through `vaultspec-core vault plan step check` and aligned the AFR register row.

## Outcome

`AFR-158` is closed as `remote-mirror`. The translator remains a non-persistent expression compiler and does not perform storage, remote I/O, logging, credential handling, or environment access. Its failure surface now routes through the registered AEAT error type with localized, redacted diagnostics.

Validation passed:

- `uv run --no-sync ruff check src/aeat/application/storage/calc_sheets/_translator.py src/aeat/application/storage/calc_sheets/test_translator_hardening.py src/aeat/application/storage/calc_sheets/test_layout_hardening.py`
- `uv run --no-sync pytest -q src/aeat/application/storage/calc_sheets/test_translator_hardening.py src/aeat/application/storage/calc_sheets/test_layout_hardening.py src/aeat/application/storage/calc_sheets/test_modelo_export_parity.py src/aeat/application/storage/calc_sheets/test_modelo_export_formatting.py src/aeat/adapters/outbound/google/test_calc_sheets_export_integration.py`
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit`

## Notes

The constructor-level hardening intentionally leaves existing static developer hints intact on `TranslationError.hint`; those hints are not part of the rendered primary error text or structured error context.
