---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-27-schema-hardening-casilla-continuity-contract-plan]]'
  - '[[2026-05-27-schema-hardening-casilla-continuity-contract-adr]]'
---



# `schema-hardening` Code Review

Reviewed P01.S03 implementation for public registry continuity exports and
private-helper boundary enforcement.

No CRITICAL, HIGH, MEDIUM, or LOW findings.

Scope reviewed:

- `src/aeat/domain/calculations/registry/__init__.py`
- `src/aeat/domain/calculations/registry/test_public_api_boundaries.py`
- `src/aeat/application/modelo/test_verification_substance.py`
- `src/aeat/domain/fincas/test_imputacion_parameters.py`
- `src/aeat/domain/iva/test_legal_basis_binding.py`

Checks reviewed:

- `uv run --no-sync ruff check src/aeat/domain/calculations/registry/__init__.py src/aeat/domain/calculations/registry/test_public_api_boundaries.py src/aeat/application/modelo/test_verification_substance.py src/aeat/domain/fincas/test_imputacion_parameters.py src/aeat/domain/iva/test_legal_basis_binding.py`
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_public_api_boundaries.py -q`
- `uv run --no-sync pytest src/aeat/application/modelo/test_verification_substance.py::test_runtime_evaluator_recognises_every_known_predicate_operator src/aeat/domain/fincas/test_imputacion_parameters.py::test_missing_lirpf_art_85_parameter_raises_finca_validation_error src/aeat/domain/iva/test_legal_basis_binding.py::test_liva_art_161_missing_recargo_parameter_raises_iva_catalogue_error -q`
