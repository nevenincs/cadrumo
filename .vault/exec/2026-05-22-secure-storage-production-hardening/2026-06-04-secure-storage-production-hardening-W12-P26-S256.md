---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S256'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s256-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S256`

Closed `AFR-154` for the calc-sheets export-plan engine.

## Description

- Reviewed `src/aeat/application/storage/calc_sheets/_engine.py` as a pure export-plan builder for the Google Sheets remote-mirror boundary.
- Removed raw registry rounding and dated-parameter details from operator-facing `CalcSheetsEngineError` strings while preserving structured context and translated-message keys.
- Moved guide text, workbook labels, anchor labels, protected-range descriptions, and the guide title behind `tr()` locale keys.
- Added real registry-backed tests proving English output-language selection flows into workbook labels, protected descriptions, guide text, and hardened engine errors.
- Updated locale catalogues through `python -m aeat.locales`.
- Closed `S256` through `vaultspec-core vault plan step check`.

## Outcome

`AFR-154` is closed as `remote-mirror`. The engine remains a deterministic in-memory plan builder: it does not persist credentials, profile data, local files, or remote state. The hardening makes the operator-facing workbook surface locale-owned and keeps raw registry implementation tokens out of primary exception messages while retaining structured diagnostic context for the core error pipeline.

Validation passed:

- `uv run --no-sync ruff check src/aeat/application/storage/calc_sheets/_engine.py src/aeat/application/storage/calc_sheets/test_engine_hardening.py`
- `uv run --no-sync pytest -q src/aeat/application/storage/calc_sheets/test_engine_hardening.py src/aeat/test_calc_sheets_error_hierarchy.py`
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit`

## Notes

The workbook tab enum values remain schema identifiers for the apply/pull adapters. This step did not rename tabs or change the remote worksheet contract.
