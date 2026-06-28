---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-27'
modified: '2026-05-27'
related:
  - '[[2026-05-27-schema-hardening-m308-standardization-plan]]'
  - '[[2026-05-27-schema-hardening-m100-validation-repair-exec]]'
---



# `schema-hardening` `m202-label-drift-repair`

Closed the strict cross-revision label drift found in Modelo 202.

## Description

The current production drift validator only compares overlapping revision
windows, so a stricter inventory pass was run across repeated casilla ids
regardless of revision overlap. Modelo 202 had seven repeated casilla ids
whose `label` values diverged between the historical and current revision
families.

The repair normalizes the current revision labels back to the stable
historical labels for casillas `04`, `19`, `26`, `40`, `47`, `48`, and
`49`. A strict M202-only drift scan now reports zero divergences across
`label`, `section`, `data_type`, `semantic_role`, and `legal_refs`.

The full backend cross-revision validation gate remains affected by active
M100 2024 WIP source-citation failures; that is tracked as a separate repair
edge.

## Tests

Passed:

`uv run --no-sync pytest src/aeat/domain/calculations/registry/test_modelo_202_registry.py -q`

Passed:

Strict M202 drift scan over `label`, `section`, `data_type`,
`semantic_role`, and `legal_refs`: `m202_strict_divergences 0`.

Observed unrelated failure:

`uv run --no-sync pytest src/aeat/domain/calculations/registry/test_modelo_202_registry.py src/aeat/domain/calculations/registry/test_cross_revision_drift.py -q`

Result: M202 tests passed; two backend corpus validation tests failed on
M100 2024 marriage-month source-citation text.
