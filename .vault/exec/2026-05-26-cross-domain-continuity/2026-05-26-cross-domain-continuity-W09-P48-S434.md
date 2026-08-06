---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-11'
modified: '2026-07-17'
body_hash: 'sha256:1541b3d79fb9a5d7390d3aed89ab98839292f5b6c5b45e32c401a15091c91e80'
step_id: 'S434'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# Promote M347_THRESHOLD_EUR through the aeat.core facade, migrate all five cross-package consumers, remove the domain row-model re-export, and prove direct imports respect the boundary.

## Scope

- `src/aeat/core/{__init__.py`
- `external_constants.py} src/aeat/application/{modelo/_calculate_input.py`
- `aggregation/_counterpart.py} src/aeat/domain/{modelos/_row_models.py`
- `calculations/registry/_counterpart_bindings.py`
- `calculations/registry/_invoice_bindings.py} src/aeat/**/tests/`

## Description

- Used the RAG index and source tracing to confirm `M347_THRESHOLD_EUR` has one authority in `core.external_constants` and five production consumers outside that module.
- Re-exported the core-owned threshold from the public `aeat.core` facade.
- Migrated application calculation input, application counterpart aggregation, two calculation-registry bindings, and the Modelo 347 row model to the public facade.
- Removed the row-model `__all__` re-export and migrated five direct test imports to the same public boundary.
- Extended the core centralisation contract to prove facade identity with the canonical constant and use by every production consumer.
- Added an AST/source-level regression that requires each production consumer to import the threshold from its relative `core` facade, rejects private-leaf imports, and verifies the row-model `__all__` exclusion.
- Ran the focused real-behavior suites, owned Ruff, a scoped whitespace check, and a repository search for remaining cross-package threshold imports.

## Outcome

- `M347_THRESHOLD_EUR` now crosses package boundaries only through `aeat.core`; core remains the sole owner.
- No cross-package production or direct test import of that threshold remains from `core.external_constants`, and the domain row-model no longer republishes it.
- The focused suite passed 61 tests in 26.36 seconds; owned Ruff and whitespace checks passed.

## Notes

- The broader import-hygiene gate has three unrelated failures from untracked private test imports and pre-existing prorrata multi-facade exports. None overlap this step; they were not changed.
