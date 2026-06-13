---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-22'
modified: '2026-05-22'
related:
  - '[[2026-05-21-schema-hardening-plan]]'
---

# `schema-hardening` `W13.P34` summary

Removed broad legal-reference warning equivalence and replaced hidden
suppression with explicit, source-grounded singleton markers.

- Modified: `src/aeat/domain/calculations/registry/_validate_semantic_roles.py`
- Modified: `src/aeat/domain/calculations/registry/test_semantic_role.py`
- Modified: `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/casillas`
- Created: `.vault/exec/2026-05-21-schema-hardening/2026-05-21-schema-hardening-W13-P34-summary.md`

## Description

The phase removed generic stripping for legal-reference tokens and marked the
current legitimate singleton roles in Modelo 200 source data. Regression tests
now preserve the boundary that article, transitional-provision, RDLeg, and LIS
markers are not typo-warning axes by default.

## Tests

`uv run pytest src/aeat/domain/calculations/registry/test_semantic_role.py src/aeat/domain/calculations/registry/test_cross_revision_drift.py::test_singleton_semantic_role_warning_count_does_not_regress -q`

`uv run pytest src/aeat/domain/calculations/registry/test_modelo_200_registry.py src/aeat/domain/calculations/registry/test_committed_registry.py -q`

`uv run ruff check src/aeat/domain/calculations/registry/_validate_semantic_roles.py src/aeat/domain/calculations/registry/test_semantic_role.py`
