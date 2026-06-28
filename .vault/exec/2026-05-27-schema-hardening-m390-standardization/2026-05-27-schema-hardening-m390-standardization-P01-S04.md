---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-27'
modified: '2026-05-27'
step_id: 'S04'
related:
  - '[[2026-05-27-schema-hardening-m390-standardization-plan]]'
---

# `schema-hardening-m390-standardization` `P01.S04`

Recorded review outcome, standardization baseline, and the next single-file
normalization edge after the M390 split.

- Created: `.vault/audit/2026-05-27-schema-hardening-m390-standardization-review.md`
- Verified: `src/aeat/_data/registry/aeat/modelos/390`

## Description

The review found no loader/schema regression and no per-modelo behavior. The
M390 split was mechanical: the fragment stream is line-identical to the
pre-split `390.toml` source, and the implementation did not modify `_loader.py`,
`_schema.py`, or `_validate.py`.

The post-split baseline is:

- M390 has no `390.toml` single-file source.
- M390 has one fragment-directory revision source.
- M390 has 15 TOML fragments.
- Largest M390 TOML fragment: 182 lines.
- Largest remaining single-file modelo: M322 at 573 lines.

Next edge: M322 should be the next standardization target unless the planned
file-size/row-size creep gate identifies a more urgent candidate.

## Tests

Validation completed:

- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_modelo_390_registry.py src/aeat/domain/calculations/registry/test_loader_directory_mode.py src/aeat/domain/calculations/registry/test_committed_registry.py src/aeat/domain/calculations/registry/test_referential_integrity.py src/aeat/domain/calculations/registry/test_ledger_iva_aggregation_binding.py::test_modelo_390_annual_iva_pipeline_resolves_binding_chain_from_four_303_filings src/aeat/application/calculations/test_binding_prefill.py::test_modelo_390_prefill_compares_annual_totals_to_persisted_periodic_observations src/aeat/application/filing/test_modelo_303_390.py -q`
- `129 passed in 124.76s`
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-05-27-schema-hardening-m390-standardization-plan.md`
- `uv run --no-sync vaultspec-core vault check frontmatter --feature schema-hardening`
- `uv run --no-sync vaultspec-core vault check body-links --feature schema-hardening`
