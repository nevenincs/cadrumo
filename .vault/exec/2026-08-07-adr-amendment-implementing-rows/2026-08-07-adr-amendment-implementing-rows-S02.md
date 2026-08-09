---
tags:
  - '#exec'
  - '#adr-amendment-implementing-rows'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:cb041b6542912423829744a17eaea0b25d1247f374e01b488038cfd3a31c2737'
step_id: 'S02'
related:
  - "[[2026-08-07-adr-amendment-implementing-rows-plan]]"
---

# Re-route Modelo 390's intra-community-acquisition categories from the inversion-del-sujeto-pasivo line to the dedicated AIC box ladders, per the 2026-08-06 amendment to modelo-iva-routing-carry-adr, and close its two cross-modelo residues (AIC base imponible reaching no official box on M390 or M303, and the AIC binding's rate_kinds omitting zero on both)

## Scope

- `src/cadrumo/registry/aeat/modelos/390/`

## Description

- Admit `zero` in the three Modelo 303 AIC selectors for devengado cuota, devengado base, and deducible cuota.
- Prove zero-rate AIC bases reach their dedicated M390 box layer and Modelo 303 box 10 through the real registry compiler and resolver.
- Add scratch-registry mutations that remove each zero-rate base selector and prove the live base assertion no longer holds.

## Outcome

The existing Modelo 390 dedicated AIC ladders and base exports were preserved and are now covered for zero-rate AIC rows. Modelo 303 now admits zero-rate AIC rows across its semantic and official-box bindings, so their non-zero base reaches the box-10 base projection while the cuota remains zero.

## Verification

- `uv run --no-sync ruff check src/cadrumo/domain/calculations/registry/tests/test_modelo_303_aic_box_10_base_projection.py src/cadrumo/domain/calculations/registry/tests/test_modelo_390_aic_isp_routing_split.py`
  `All checks passed!`
- `uv run --no-sync pytest -n 0 -m unit src/cadrumo/domain/calculations/registry/tests/test_modelo_303_aic_box_10_base_projection.py src/cadrumo/domain/calculations/registry/tests/test_modelo_390_aic_isp_routing_split.py`
  `11 passed in 4.93s`
- `uv run --no-sync pytest -n 0 -m unit src/cadrumo/domain/calculations/registry/tests/test_ledger_iva_aggregation_binding_reverse_charge.py src/cadrumo/domain/calculations/registry/tests/test_modelo_303_registry.py src/cadrumo/domain/calculations/registry/tests/test_modelo_390_registry.py src/cadrumo/domain/calculations/registry/tests/test_modelo_390_base_imponible_bindings.py`
  `70 passed in 12.77s`

## Notes

- The pre-existing plan scope names a retired registry location; the implementation uses the current registry authoring tree.
