---
tags:
  - '#exec'
  - '#cross-period-prorrata'
date: '2026-07-06'
modified: '2026-07-08'
step_id: 'S44'
related:
  - "[[2026-07-06-cross-period-prorrata-plan]]"
---

# ground the Modelo 390 annual regularizacion target, declare its future prorrata_regularizacion binding/export grounding, keep box 522 manual until S45/S46 materialise values, and include 522 in the annual deductible total formula

## Scope

- `src/aeat/_data/registry/aeat/modelos/390/revisions/2010-y-siguientes/`
- `src/aeat/domain/calculations/registry/tests/`

## Description

- Ground the claimed Modelo 390 target in the bundled AEAT 2025 record design:
  page `04000`, field `[522]`, offset `642`, length `17`, type `N`,
  "Regularización por aplicación porcentaje definitivo de prorrata".
- Provision `iva.anual.regularizacion-prorrata-definitiva` as the canonical
  Modelo 390 casilla for that official field, while keeping it
  operator-supplied (`input_kind = "manual"`) until the live resolver can
  materialise values without a silent zero.
- Add `modelo-390-prorrata-regularizacion-anual` with source
  `prorrata_regularizacion`, the same full-year Modelo 303 source casilla set as
  the Modelo 303 casilla 44 binding, and selector output
  `modelo_390_regularizacion_anual`.
- Extend the existing prorrata regularizacion selector output literal set; no new
  source kind, resolver convention, or validator convention was introduced.
- Add the page 04 export-layout field, construct membership, and
  calculation-completeness manifest coverage for box `[522]`.
- Include box `[522]` in `modelo-390-iva-anual-cuota-deducible-total` so a
  nonzero regularizacion affects box `[64]` and then box `[65]`.
- Update the M390 registry and annual calculation tests to prove the honest
  interim state, the future binding selector/export grounding, and the nonzero
  box `[522]` flow without duplicating formula logic.

## Outcome

- S44 now provisions the real Modelo 390 box `[522]` target and binding row, but
  does not make the casilla a live bound projection while
  `prorrata_regularizacion` is deferred.
- The M390 annual deductible formula now consumes box `[522]`; resolver timing
  and automatic value materialisation remain with `W07.P11.S45` and
  `W07.P11.S46`.
- The follow-up S44 audit finding is resolved for this slice: no live bound 522
  silent-zero path remains, and nonzero operator-supplied 522 changes boxes
  `[64]` and `[65]`.
- Focused gates passed:
  `uv run --no-sync ruff check src/aeat/domain/calculations/registry/_bindings.py src/aeat/domain/calculations/registry/tests/test_selector_shape.py src/aeat/domain/calculations/registry/tests/test_modelo_390_registry.py src/aeat/domain/calculations/registry/tests/test_m390_2024_annual_manual_worked_example.py`;
  `uv run --no-sync pytest -q src/aeat/domain/calculations/registry/tests/test_modelo_390_registry.py src/aeat/domain/calculations/registry/tests/test_m390_2024_annual_manual_worked_example.py src/aeat/domain/calculations/registry/tests/test_selector_shape.py`;
  `uv run --no-sync vaultspec-core vault check frontmatter --feature cross-period-prorrata`;
  `uv run --no-sync vaultspec-core vault check features --feature cross-period-prorrata`;
  `uv run --no-sync vaultspec-core vault plan check cross-period-prorrata`.

## Notes

- Automatic `prorrata_regularizacion` resolver materialisation remains deferred
  to `W07.P11.S45` and `W07.P11.S46`; S44 is target provisioning plus formula
  membership only.
- The feature index was rebuilt with
  `uv run --no-sync vaultspec-core vault feature index -f cross-period-prorrata`
  after the feature check reported it stale.
