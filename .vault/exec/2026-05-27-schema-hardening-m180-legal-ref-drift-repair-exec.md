---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-27'
modified: '2026-05-27'
related:
  - '[[2026-05-27-schema-hardening-m308-standardization-plan]]'
  - '[[2026-05-27-schema-hardening-m202-label-drift-repair-exec]]'
  - '[[2026-05-27-schema-hardening-m100-marriage-citation-repair-exec]]'
---



# `schema-hardening` `m180-legal-ref-drift-repair`

Closed the strict cross-revision legal-reference drift found in Modelo 180.

## Description

The strict repeated-casilla inventory showed Modelo 180 had thirty
`legal_refs` divergences between the 2019-2022 and 2023-y-siguientes
revision families. The drift was the missing `orden-hfp-1284-2023:art-7`
reference on the older revision's repeated casillas.

The repair adds that reference to the thirty 2019-2022 casilla fragments.
The validation pass then exposed a real construct dependency: the
2019-2022 `modelo-180-annual-summary` construct also had to include the
same reference for the three declaration-total casillas it owns.

After the construct repair, the strict M180-only drift scan reports zero
divergences across `label`, `section`, `data_type`, `semantic_role`, and
`legal_refs`.

The remaining strict drift debt is concentrated in Modelo 100, whose active
profile and revision-hardening WIP is being handled separately.

## Tests

Initial failed gate, not swallowed:

`uv run --no-sync pytest src/aeat/domain/calculations/registry/test_modelo_180_registry.py src/aeat/domain/calculations/registry/test_cross_revision_drift.py -q`

Result: seven failures. The backend validator rejected
`modelo-180-annual-summary` because it did not include
`orden-hfp-1284-2023:art-7` required by `decl.total-perceptores`,
`decl.base-total`, and `decl.retenciones-total`.

Passed after construct repair:

`uv run --no-sync pytest src/aeat/domain/calculations/registry/test_modelo_180_registry.py src/aeat/domain/calculations/registry/test_cross_revision_drift.py -q`

Result: 18 passed.

Passed:

Strict M180 drift scan over `label`, `section`, `data_type`,
`semantic_role`, and `legal_refs`: `m180_strict_counts {}`.
