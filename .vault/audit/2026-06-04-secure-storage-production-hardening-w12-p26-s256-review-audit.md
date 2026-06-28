---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-W12-P26-S256]]'
---

# `secure-storage-production-hardening` `W12.P26.S256` Review

## S256-001 | HIGH | Workbook operator text bypassed the locale layer

The calc-sheets engine emitted guide text, labels, anchor labels, and protected-range descriptions as hard-coded Spanish strings. Those values are operator-facing because they are written into the generated workbook and can be mirrored to Google Sheets. The engine now resolves them through `tr()` keys, and `test_workbook_operator_labels_resolve_through_output_language` proves the plan reflects the configured output language.

## S256-002 | MEDIUM | Engine errors rendered raw registry tokens in primary messages

Unsupported rounding codes and missing scalar-parameter cases previously interpolated raw registry values into the exception string. The errors now use stable primary messages with translated-message keys and structured context so the core error pipeline can render/redact details consistently.

## S256-003 | PASS | Remote-mirror classification is retained

`build_export_plan` remains a pure plan-construction boundary. It reads a validated registry snapshot and caller-supplied operator inputs/relation values, then returns a `SheetExportPlan`; persistence, Google API writes, and pull reconciliation remain owned by the outbound adapters.

## S256-004 | PASS | Validation

- `uv run --no-sync ruff check src/aeat/application/storage/calc_sheets/_engine.py src/aeat/application/storage/calc_sheets/test_engine_hardening.py` passed.
- `uv run --no-sync pytest -q src/aeat/application/storage/calc_sheets/test_engine_hardening.py src/aeat/test_calc_sheets_error_hierarchy.py` passed with 15 tests.
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit` passed.

Disposition: close `AFR-154` as `remote-mirror` with calc-sheets engine text and error surfaces centralized.
