---
tags:
  - '#exec'
  - '#core-authority'
step_id: S67
date: '2026-05-31'
modified: '2026-05-31'
related:
  - '[[2026-05-31-core-authority-plan]]'
  - '[[2026-05-31-core-authority-adr]]'
---

# core-authority W07.P19.S67 - remove domain.calculations passthrough re-exports

## Outcome

Verified that all 5 callers of the 6 passthrough symbols in `domain/calculations/__init__.py`
(RegistryCatalogues, RegistrySnapshot, RegistryValidator, build_snapshot, load_modelo_file,
load_registry_tree) already import directly from `domain.calculations.registry.*`. Removed
all 6 re-export symbols and the `__all__` list from `domain/calculations/__init__.py`.
Retained only the package docstring. RELOC-039, Rule 9-B.

Before: 22-line init with from .registry import + __all__ = [...6 symbols...]
After: 1-line init (docstring only)

## Commit

`33eac6da5` — refactor(calculations): W07.P19.S63-S67

## Files touched

- `src/aeat/domain/calculations/__init__.py` — 20 lines deleted

## Verification

`uv run pytest src/aeat/domain/calculations/registry/test_authority.py src/aeat/domain/calculations/registry/test_casilla_observation.py src/aeat/domain/calculations/registry/test_applicability_canonical.py -q` — 18 passed.

Pre-existing failures (`test_catalogue_verification::test_committed_registry_tree_has_required_model_law_coverage` and `test_public_api_boundaries::test_source_tree_does_not_use_absolute_registry_private_imports`) are unrelated to this step and were failing before W07.
