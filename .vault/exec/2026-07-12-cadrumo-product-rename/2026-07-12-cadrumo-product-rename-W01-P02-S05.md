---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-12'
step_id: 'S05'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# Add the immutable canonical Cadrumo tuple and authority-boundary vocabulary

## Scope

- `src/cadrumo/core/product_identity.py`

## Description

- Re-read the accepted rename research, ADR, plan, environment matrix, persistence matrix, and current `HEAD`.
- Locate the existing committed compatibility regime and frozen-value conventions with semantic discovery, whole-file reads, and exact searches.
- Add one import-light immutable identity tuple and one closed product-versus-authority referent vocabulary without aliases or fallbacks.
- Validate the new module with focused syntax and lint checks before closing the Step.

## Outcome

Added `src/cadrumo/core/product_identity.py` as the sole authored identity authority for this Step. Its public API is:

- `ProductIdentity`, an immutable `NamedTuple` whose fields cover display name, package, distribution, CLI, repository, MCP server/executable/tool/resource identities, plugin identifier, environment prefix, companion distributions, and companion namespace.
- `PRODUCT_IDENTITY`, the canonical tuple fixed to `Cadrumo`, `cadrumo`, `cadrumo-mcp`, `CADRUMO_`, `cadrumo-data-manuals`, `cadrumo-data-official`, and `cadrumo_data` exactly as accepted.
- `IdentityReferent`, a closed `StrEnum` with only `CADRUMO_PRODUCT` and `AEAT_AUTHORITY`.
- `AEAT_AUTHORITY_SHORT_NAME`, the retained legal short name for the external authority referent.

The module has no dependency on settings, environment state, storage, outer layers, or the former product package. It contains no old import alias, executable alias, environment fallback, namespace fallback, or migration path. The later facade and contract-test Steps remain untouched.

## Notes

- Scoped status and diff inspection found no pre-existing `src/cadrumo/core/product_identity.py` and no overlapping work before creation.
- The `src/cadrumo/core` directory did not previously exist; this Step creates only the planned module path, not package facade files.
