---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-12'
body_hash: 'sha256:27119c28d0917ffa16115d4d82cf6e361dc53483b995e537b96306eeae27ffaf'
step_id: 'S06'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# Expose the public product identity through the package facade

## Scope

- `src/cadrumo/core/__init__.py`

## Description

- Read the approved plan and current `HEAD`, then verify no overlapping facade work existed.
- Locate facade conventions semantically, read the existing core facade in full, and confirm eager re-export and `__all__` patterns exactly.
- Re-export the four S05 identity symbols through the Cadrumo core package without aliases or additional behavior.
- Prove direct facade imports, syntax, lint, formatting, and export identity before closing the Step.

## Outcome

Added `src/cadrumo/core/__init__.py` as an import-light public facade over `product_identity`. It eagerly re-exports `ProductIdentity`, `PRODUCT_IDENTITY`, `IdentityReferent`, and `AEAT_AUTHORITY_SHORT_NAME`, and declares those exact four names in typed `__all__`.

The facade creates no duplicate identity values, lazy alias, former-product spelling, compatibility fallback, root `cadrumo` package facade, or test surface. Direct imports return the exact leaf-module objects.

## Notes

- Scoped status and diff inspection found no pre-existing `src/cadrumo/core/__init__.py` before creation.
- Tests remain assigned to S07 and the root package facade remains outside this Step.
