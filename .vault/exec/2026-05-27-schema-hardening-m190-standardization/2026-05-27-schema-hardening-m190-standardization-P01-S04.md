---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-27'
modified: '2026-05-27'
step_id: 'S04'
related:
  - '[[2026-05-27-schema-hardening-m190-standardization-plan]]'
---

# `schema-hardening-m190-standardization` `P01.S04`

Recorded review outcome, standardization baseline, and the next single-file
normalization edge after the M190 split.

- Created: `.vault/audit/2026-05-27-schema-hardening-m190-standardization-review.md`
- Verified: `src/aeat/_data/registry/aeat/modelos/190`

## Description

The review found no loader/schema regression and no per-modelo behavior. The
M190 split was mechanical: the fragment stream is line-identical to the
pre-split `190.toml` source, and the implementation did not modify `_loader.py`,
`_schema.py`, or `_validate.py`.

The post-split baseline is:

- M190 has no `190.toml` single-file source.
- M190 has one fragment-directory revision source.
- M190 has 15 TOML fragments.
- Largest M190 TOML fragment: 285 lines.
- Largest remaining single-file modelo: M115 at 989 lines.

Next edge: M115 should be the next standardization target unless the planned
file-size/row-size creep gate identifies a more urgent candidate.

## Tests

Validation completed:

- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_modelo_190_registry.py src/aeat/domain/calculations/registry/test_modelo_190_193_round_trip.py src/aeat/domain/calculations/registry/test_loader_directory_mode.py src/aeat/domain/calculations/registry/test_committed_registry.py src/aeat/domain/calculations/registry/test_referential_integrity.py src/aeat/domain/calculations/registry/test_modelo_chain_resolution.py src/aeat/domain/calculations/registry/test_detail_record_modelo_coverage.py src/aeat/domain/calculations/registry/test_cross_dependency_calculations.py::test_modelo_190_calculation_resolves_modelo_111_quarterly_filings -q`
- `134 passed in 119.36s`
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-05-27-schema-hardening-m190-standardization-plan.md`
- `uv run --no-sync vaultspec-core vault check frontmatter --feature schema-hardening`
- `uv run --no-sync vaultspec-core vault check body-links --feature schema-hardening`
