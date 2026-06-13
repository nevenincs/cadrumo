---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-27'
modified: '2026-05-27'
step_id: 'S03'
related:
  - '[[2026-05-27-schema-hardening-m720-standardization-plan]]'
---

# `schema-hardening-m720-standardization` `P01.S03`

Verified M720 directory loading, registry integrity, detail-record behavior,
deadline/file schedule behavior, and file-size reduction after the split.

- Verified: `src/aeat/_data/registry/aeat/modelos/720`
- Verified: `src/aeat/domain/calculations/registry/test_modelo_720_registry.py`
- Verified: `src/aeat/domain/calculations/registry/test_committed_registry.py`
- Verified: `src/aeat/domain/calculations/registry/test_referential_integrity.py`
- Verified: `src/aeat/application/calculations/test_row_set_assembly.py`

## Description

M720 now loads through the generic directory-mode loader with one
fragment-directory revision. The split reduced the M720 review surface from a
950-line single file to 16 TOML fragments, with the largest fragment at 301
lines.

Current registry file-size baseline:

- `720.toml` exists: false.
- M720 fragment count: 16.
- Largest M720 fragment: 301 lines.
- Largest remaining single-file modelo: M390 at 808 lines.

Remaining single-file modelos by line count:

- M390: 808
- M322: 573
- M353: 569
- M184: 483
- M193: 472
- M309: 363
- M347: 356
- M360: 324
- M036: 283
- M840: 210
- M308: 194

## Tests

An initial broad pytest command failed before exercising the target surface
because it referenced a non-existent test node,
`test_modelo_720_foreign_asset_rows_preserve_typed_values`. The intended row
assembly test names were collected and the corrected gate was rerun.

Validation completed:

- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_modelo_720_registry.py src/aeat/domain/calculations/registry/test_loader_directory_mode.py src/aeat/domain/calculations/registry/test_committed_registry.py src/aeat/domain/calculations/registry/test_referential_integrity.py src/aeat/domain/calculations/registry/test_detail_record_modelo_coverage.py src/aeat/domain/calculations/registry/test_detail_record_row_builders.py src/aeat/application/calculations/test_row_set_assembly.py::test_assemble_foreign_asset_parses_iso_acquisition_date src/aeat/application/calculations/test_row_set_assembly.py::test_assemble_observations_for_grouping_dispatches_foreign_asset src/aeat/application/calculations/test_detail_record_round_trip.py::test_modelo_720_foreign_asset_round_trip_preserves_dates_and_currency -q`
- `154 passed in 99.55s`
