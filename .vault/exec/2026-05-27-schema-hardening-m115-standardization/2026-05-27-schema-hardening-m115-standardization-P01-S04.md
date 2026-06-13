---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-27'
modified: '2026-05-27'
step_id: 'S04'
related:
  - '[[2026-05-27-schema-hardening-m115-standardization-plan]]'
---

# `schema-hardening-m115-standardization` `P01.S04`

Recorded review outcome, standardization baseline, and the next single-file
normalization edge after the M115 split.

- Created: `.vault/audit/2026-05-27-schema-hardening-m115-standardization-review.md`
- Verified: `src/aeat/_data/registry/aeat/modelos/115`

## Description

The review found no loader/schema regression and no per-modelo behavior. The
M115 split was mechanical: the fragment stream is line-identical to the
pre-split `115.toml` source, and the implementation did not modify `_loader.py`,
`_schema.py`, or `_validate.py`.

The post-split baseline is:

- M115 has no `115.toml` single-file source.
- M115 has one fragment-directory revision source.
- M115 has 14 TOML fragments.
- Largest M115 TOML fragment: 525 lines.
- Largest remaining single-file modelo: M720 at 950 lines.

Next edge: M720 should be the next standardization target unless the planned
file-size/row-size creep gate identifies a more urgent candidate.

## Tests

Validation completed:

- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_modelo_115_registry.py src/aeat/domain/calculations/registry/test_modelo_115_round_trip.py src/aeat/domain/calculations/registry/test_loader_directory_mode.py src/aeat/domain/calculations/registry/test_committed_registry.py src/aeat/domain/calculations/registry/test_referential_integrity.py src/aeat/application/filing/test_filing.py::test_build_draft_uses_registry_snapshot_for_modelo_115 src/aeat/application/filing/test_filing.py::test_approve_modelo_115_draft_uses_registry_schema_fingerprint src/aeat/application/filing/test_export.py::test_export_writes_modelo_115_registry_layout src/aeat/application/filing/test_export.py::test_verify_matches_exported_modelo_115_layout src/aeat/application/verification/test_verify.py::test_verify_declaracion_uses_modelo_115_registry_snapshot -q`
- `120 passed in 121.12s`
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-05-27-schema-hardening-m115-standardization-plan.md`
- `uv run --no-sync vaultspec-core vault check frontmatter --feature schema-hardening`
- `uv run --no-sync vaultspec-core vault check body-links --feature schema-hardening`
