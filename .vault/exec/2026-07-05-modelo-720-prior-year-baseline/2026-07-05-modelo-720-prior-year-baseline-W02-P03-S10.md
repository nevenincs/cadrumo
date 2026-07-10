---
tags:
  - '#exec'
  - '#modelo-720-prior-year-baseline'
date: '2026-07-05'
modified: '2026-07-05'
step_id: 'S10'
related:
  - "[[2026-07-05-modelo-720-prior-year-baseline-plan]]"
---

# Update the central foreign-asset class taxonomy tests to pin the official M720 clave set and any Modelo 721 split

## Scope

- `src/aeat/core/tests/test_foreign_asset_obligation.py`

## Description

- Updated the core obligation tests so every `ForeignAssetClass` remains mapped to a regulatory obligation group.
- Added coverage proving the new IIC class maps to the RD 1065/2007 art. 42 ter valores/derechos/seguros block.
- Added a central official-code test pinning the Modelo 720 position-102 code map to `C`, `V`, `I`, `S`, and `B`.
- Added coverage proving `VIRTUAL_CURRENCY` is excluded from the Modelo 720 code map and remains a Modelo 721 split.

## Outcome

- The core taxonomy test now fails if a future worker removes IIC, maps real estate back to `I`, or leaks virtual currency into Modelo 720.
- The existing totality test continues to guard that every enum member has an obligation group.

## Notes

- Focused verification passed: `uv run --no-sync pytest -q -n 0 src/aeat/core/tests/test_foreign_asset_obligation.py src/aeat/application/aggregation/tests/test_foreign_assets.py --tb=short` reported 42 passed.
- Broader phase verification passed with `src/aeat/application/aggregation/tests/test_per_modelo_service.py` included and reported 67 passed.
- Focused ruff verification passed on the touched source and test files.
