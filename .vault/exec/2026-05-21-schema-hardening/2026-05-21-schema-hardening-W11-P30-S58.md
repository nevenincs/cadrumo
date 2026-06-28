---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-22'
modified: '2026-05-22'
step_id: 'S58'
related:
  - '[[2026-05-21-schema-hardening-plan]]'
---

# `schema-hardening` `W11.P30.S58`

Implemented exact-family generated/pending warning-sidecar recognition for
approved Modelo 100 families.

- Modified: `src/aeat/domain/calculations/registry/_validate_semantic_roles.py`
- Created: `.vault/exec/2026-05-21-schema-hardening/2026-05-21-schema-hardening-W11-P30-S58.md`

## Description

The validator now recognizes generated/pending suffixes only inside the
approved `c_valenciana_autoconsumo`, `murcia_infraestructuras`, and
`madrid_nuevos_contribuyentes` family bases. The change is warning-only and
does not rewrite registry roles.

## Tests

`uv run ruff check src/aeat/domain/calculations/registry/_validate_semantic_roles.py src/aeat/domain/calculations/registry/test_semantic_role.py`

`uv run pytest src/aeat/domain/calculations/registry/test_semantic_role.py src/aeat/domain/calculations/registry/test_cross_revision_drift.py::test_singleton_semantic_role_warning_count_does_not_regress -q`
