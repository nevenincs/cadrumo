---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S257'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s257-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S257`

Closed `AFR-155` for the calc-sheets layout planner.

## Description

- Reviewed `src/aeat/application/storage/calc_sheets/_layout.py` as a pure registry-to-cell layout planner classified `remote-mirror`.
- Replaced bare `KeyError` resolver failures with typed `CalcSheetsEngineError` instances carrying a locale key and non-sensitive structured context.
- Replaced silent skips for referenced-but-undeclared bindings, date bindings, parameters, and relations with typed layout failures.
- Updated the translator boundary to catch typed layout errors and preserve its public `TranslationError` contract without rendering raw formula reference tokens.
- Enrolled the layout error locale key through `python -m aeat.locales`.
- Added real pydantic-record tests for typed layout failures and translator wrapping.
- Closed `S257` through `vaultspec-core vault plan step check`.

## Outcome

`AFR-155` is closed as `remote-mirror`. The layout planner remains deterministic and non-persistent, while unresolved and undeclared layout references now surface through the core AEAT exception hierarchy rather than bare `KeyError` or silent omission. Translator-facing failures no longer echo caller or corrupted-registry reference tokens in the exception message.

Validation passed:

- `uv run --no-sync ruff check src/aeat/application/storage/calc_sheets/_layout.py src/aeat/application/storage/calc_sheets/_translator.py src/aeat/application/storage/calc_sheets/test_layout_hardening.py src/aeat/application/storage/calc_sheets/test_engine_hardening.py`
- `$env:PYTHONPATH='src'; uv run --no-sync pytest -q src/aeat/application/storage/calc_sheets/test_layout_hardening.py src/aeat/application/storage/calc_sheets/test_engine_hardening.py src/aeat/application/storage/calc_sheets/test_modelo_export_parity.py src/aeat/application/storage/calc_sheets/test_modelo_export_formatting.py src/aeat/adapters/outbound/google/test_calc_sheets_export_integration.py src/aeat/adapters/outbound/google/test_grid_resize.py`
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit`

## Notes

The translator still owns many other expression-shape errors; this step only hardened the layout resolver and declaration-consistency paths used by formula reference lookup. Parameter lookup errors emitted directly in `_translator.py` are tracked by the later translator-owned row.
