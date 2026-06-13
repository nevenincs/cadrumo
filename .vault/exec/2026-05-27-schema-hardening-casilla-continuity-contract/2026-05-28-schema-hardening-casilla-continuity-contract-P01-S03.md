---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-28'
modified: '2026-05-28'
step_id: 'S03'
related:
  - '[[2026-05-27-schema-hardening-casilla-continuity-contract-plan]]'
---



# `schema-hardening` `P01.S03`

Exported the stable public registry continuity and advisory drift surface while
keeping private validator helpers unexported.

- Modified: `src/aeat/domain/calculations/registry/__init__.py`
- Modified: `src/aeat/domain/calculations/registry/test_public_api_boundaries.py`
- Modified: `src/aeat/application/modelo/test_verification_substance.py`
- Modified: `src/aeat/domain/fincas/test_imputacion_parameters.py`
- Modified: `src/aeat/domain/iva/test_legal_basis_binding.py`
- Created: `.vault/audit/2026-05-28-schema-hardening-casilla-continuity-p01-s03-review.md`

## Description

Published `CasillaContinuidadEvolutionDefinition`, the cross-revision advisory
drift report types, and the advisory drift report producer through the registry
package root. Also published the canonical verification predicate operator set
so application tests no longer import the private schema module.

The public-boundary regression now asserts that continuity report names are
exported and private cross-revision helper functions remain absent from the
package root. Existing absolute private registry imports in three tests were
replaced with public registry imports.

## Tests

- `uv run --no-sync ruff check src/aeat/domain/calculations/registry/__init__.py src/aeat/domain/calculations/registry/test_public_api_boundaries.py src/aeat/application/modelo/test_verification_substance.py src/aeat/domain/fincas/test_imputacion_parameters.py src/aeat/domain/iva/test_legal_basis_binding.py`
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_public_api_boundaries.py -q`
- `uv run --no-sync pytest src/aeat/application/modelo/test_verification_substance.py::test_runtime_evaluator_recognises_every_known_predicate_operator src/aeat/domain/fincas/test_imputacion_parameters.py::test_missing_lirpf_art_85_parameter_raises_finca_validation_error src/aeat/domain/iva/test_legal_basis_binding.py::test_liva_art_161_missing_recargo_parameter_raises_iva_catalogue_error -q`
