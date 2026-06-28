---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S258'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s258-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S258`

Closed `AFR-156` for the calc-sheets parity harness.

## Description

- Reviewed `src/aeat/application/storage/calc_sheets/_parity_harness.py` as the remote Google Sheets parity verification boundary.
- Replaced import-time `Settings()` construction with call-time `load_settings()` resolution for the Sheets recalculation delay.
- Replaced raw unknown-casilla scenario errors with `CalcSheetsParityError` carrying a translated-message key and non-sensitive structured context.
- Replaced silent seed-cell skips for missing casilla, binding, and enum-binding anchors with typed parity errors.
- Added real registry-backed parity-harness hardening tests without live Google calls, fakes, monkeypatches, skips, or xfails.
- Updated locale catalogues through `python -m aeat.locales`.
- Closed `S258` through `vaultspec-core vault plan step check` and aligned the AFR register row.

## Outcome

`AFR-156` is closed as `remote-mirror`. The harness still performs remote Google Sheets I/O only inside `verify_modelo_parity`, but adverse scenario and settings paths now route through centralized settings and the core AEAT exception hierarchy. Scenario-supplied raw casilla or binding tokens are not rendered into primary exception text.

Validation passed:

- `uv run --no-sync ruff check src/aeat/application/storage/calc_sheets/_parity_harness.py src/aeat/application/storage/calc_sheets/test_parity_harness_hardening.py`
- `uv run --no-sync pytest -q src/aeat/application/storage/calc_sheets/test_parity_harness_hardening.py src/aeat/application/storage/calc_sheets/test_modelo_export_parity.py`
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit`

## Notes

This step did not run live Google parity; the hardened behavior is covered through local registry-backed tests around scenario preparation, seed planning, and settings resolution. Live remote parity remains governed by the existing Google credentials and outbound apply adapter.
