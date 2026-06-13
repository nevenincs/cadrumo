---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-27'
modified: '2026-05-27'
step_id: 'S04'
related:
  - '[[2026-05-27-schema-hardening-m720-standardization-plan]]'
---

# `schema-hardening-m720-standardization` `P01.S04`

Recorded review outcome, standardization baseline, and the next single-file
normalization edge after the M720 split.

- Created: `.vault/audit/2026-05-27-schema-hardening-m720-standardization-review.md`
- Verified: `src/aeat/_data/registry/aeat/modelos/720`

## Description

The review found no loader/schema regression and no per-modelo behavior. The
M720 split was mechanical: the fragment stream is line-identical to the
pre-split `720.toml` source, and the implementation did not modify `_loader.py`,
`_schema.py`, or `_validate.py`.

The post-split baseline is:

- M720 has no `720.toml` single-file source.
- M720 has one fragment-directory revision source.
- M720 has 16 TOML fragments.
- Largest M720 TOML fragment: 301 lines.
- Largest remaining single-file modelo: M390 at 808 lines.

Next edge: M390 should be the next standardization target unless the planned
file-size/row-size creep gate identifies a more urgent candidate.

## Tests

Validation completed:

- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_modelo_720_registry.py src/aeat/domain/calculations/registry/test_loader_directory_mode.py src/aeat/domain/calculations/registry/test_committed_registry.py src/aeat/domain/calculations/registry/test_referential_integrity.py src/aeat/domain/calculations/registry/test_detail_record_modelo_coverage.py src/aeat/domain/calculations/registry/test_detail_record_row_builders.py src/aeat/application/calculations/test_row_set_assembly.py::test_assemble_foreign_asset_parses_iso_acquisition_date src/aeat/application/calculations/test_row_set_assembly.py::test_assemble_observations_for_grouping_dispatches_foreign_asset src/aeat/application/calculations/test_detail_record_round_trip.py::test_modelo_720_foreign_asset_round_trip_preserves_dates_and_currency -q`
- `154 passed in 99.55s`
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-05-27-schema-hardening-m720-standardization-plan.md`
- `uv run --no-sync vaultspec-core vault check frontmatter --feature schema-hardening`
- `uv run --no-sync vaultspec-core vault check body-links --feature schema-hardening`
