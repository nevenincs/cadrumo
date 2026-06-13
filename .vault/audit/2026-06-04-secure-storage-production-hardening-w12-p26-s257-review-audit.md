---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-W12-P26-S257]]'
---

# `secure-storage-production-hardening` `W12.P26.S257` Review

## S257-001 | MEDIUM | Layout resolver API raised bare KeyError

`SheetLayout.address_for*` methods were application-layer resolver APIs but raised `KeyError` with raw reference values for missing casilla, binding, date-binding, and relation anchors. They now raise `CalcSheetsEngineError` with `translated_message` and non-sensitive `reference_kind` context.

## S257-002 | MEDIUM | Translator wrapping echoed raw layout reference tokens

The translator previously caught `KeyError` for several layout lookups and interpolated the raw missing binding/date-binding/relation id into `TranslationError`. It now catches `CalcSheetsEngineError`, keeps a stable message by reference kind, and preserves the cause chain.

## S257-003 | MEDIUM | Referenced but undeclared layout inputs were silently skipped

The layout planner skipped formula references to undeclared bindings, date bindings, parameters, and relations. That could produce a layout missing required cells and defer the failure to a later translator or pull path. The planner now raises typed `CalcSheetsEngineError` with an `undeclared_reference` locale key and reference-kind context.

## S257-004 | PASS | Layout remains deterministic and non-persistent

`plan_layout` still consumes only a `ModeloRevision` and optional bracket filter date, then returns immutable pydantic layout records. No storage, remote API, logging, or environment access was added.

## S257-005 | PASS | Validation

- `uv run --no-sync ruff check src/aeat/application/storage/calc_sheets/_layout.py src/aeat/application/storage/calc_sheets/_translator.py src/aeat/application/storage/calc_sheets/test_layout_hardening.py src/aeat/application/storage/calc_sheets/test_engine_hardening.py` passed.
- `$env:PYTHONPATH='src'; uv run --no-sync pytest -q src/aeat/application/storage/calc_sheets/test_layout_hardening.py src/aeat/application/storage/calc_sheets/test_engine_hardening.py src/aeat/application/storage/calc_sheets/test_modelo_export_parity.py src/aeat/application/storage/calc_sheets/test_modelo_export_formatting.py src/aeat/adapters/outbound/google/test_calc_sheets_export_integration.py src/aeat/adapters/outbound/google/test_grid_resize.py` passed with 40 tests.
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit` passed.

Disposition: close `AFR-155` as `remote-mirror` with layout resolver exceptions hardened.
