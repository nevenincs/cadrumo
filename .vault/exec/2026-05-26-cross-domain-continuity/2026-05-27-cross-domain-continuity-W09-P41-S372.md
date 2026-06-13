---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-05-27'
modified: '2026-05-27'
step_id: 'S372'
related:
  - '[[2026-05-26-cross-domain-continuity-plan]]'
---

# `cross-domain-continuity` `W09.P41.S372`

Implemented the multi-row non-decimal CLI mechanism (Task #200) — a repeatable `--row TYPE FIELD=value ...` flag on `aeat app modelo work calculate` for M184 and M232.

## Files

- Created: `src/aeat/domain/modelos/_row_models.py` — typed pydantic row models (`Modelo184MemberRow`, `Modelo232VinculadaRow`, `ModeloDetailRow` union)
- Modified: `src/aeat/domain/modelos/__init__.py` — exports for the three new row types
- Modified: `src/aeat/domain/modelos/_calculation_revision.py` — `detail_rows` field on `CalculationRevision`, `_canonical_detail_rows()` helper, `derive_calculation_revision_id` extended with `detail_rows` parameter for content-addressed hashing
- Modified: `src/aeat/application/modelo/_actions.py` — `detail_rows` parameter threaded through `calculate_modelo_revision` and `calculate_modelo_revision_from_bucket_aggregation`
- Modified: `src/aeat/entrypoints/cli/_modelo.py` — `--row` flag, `_parse_row_spec`, `_validate_m184_share_sum`, `_ROW_TYPES_SUPPORTED`, `_ROW_DECIMAL_FIELDS` module constants
- Modified: `src/aeat/locales/es.yml`, `en.yml`, `ca.yml`, `hu.yml` — 7 locale keys under `cli.app.modelo.work` for row parsing error messages
- Created: `src/aeat/domain/modelos/test_row_models.py` — 25 tests for row model validation, immutability, and revision-ID content addressing
- Created: `src/aeat/entrypoints/cli/test_work_calculate_row_flag.py` — 19 tests for `_parse_row_spec` (valid/invalid paths including ArithmeticError safety) and `_validate_m184_share_sum` (share-sum constraint + anti-tautology proof)

## Description

Row models use `strict=True, frozen=True, extra="forbid"` pydantic v2 config. String CLI tokens for `porcentaje` and `importe` fields are coerced to `Decimal` via `_ROW_DECIMAL_FIELDS` before model construction. Invalid numeric strings (e.g., `porcentaje=abc`) are caught by an `ArithmeticError` guard in the try-block alongside `ValidationError`, `TypeError`, and `ValueError`, ensuring all error paths raise `BadParameter` rather than propagating as unhandled exceptions.

`CalculationRevision.detail_rows` carries rows as an immutable tuple in the revision record. `_canonical_detail_rows()` sorts rows by `(row_type, nif)` and normalizes `Decimal` values via `.normalize()` before SHA-256 inclusion, making revision IDs stable under insertion order while correctly distinguishing revisions with different row content.

M349 operador rows are NOT implemented: M349 derives its per-operator records automatically from the collectible-invoice ledger; there is no manual-entry path.

## Tests

All 44 new tests pass. The 6 pre-existing failures in `test_modelo.py` and `test_modelo_calculation_through_real_cli.py` are peer-agent regressions unrelated to this change (confirmed by `git diff --name-only`).

Code review gates G1-G6 all pass. One safety gap found during review (non-numeric Decimal field raised uncaught `ArithmeticError`) was fixed and covered by `test_non_numeric_decimal_field_raises`.
