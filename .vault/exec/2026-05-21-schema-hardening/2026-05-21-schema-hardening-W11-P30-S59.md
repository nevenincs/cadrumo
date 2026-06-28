---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-22'
modified: '2026-05-22'
step_id: 'S59'
related:
  - '[[2026-05-21-schema-hardening-plan]]'
---

# `schema-hardening` `W11.P30.S59`

Added regression tests for the approved and blocked generated/pending
families.

- Modified: `src/aeat/domain/calculations/registry/test_semantic_role.py`
- Created: `.vault/exec/2026-05-21-schema-hardening/2026-05-21-schema-hardening-W11-P30-S59.md`

## Description

The new tests prove that approved C Valenciana autoconsumo, Murcia
infraestructuras, and Madrid nuevos contribuyentes rows do not emit typo
warnings. They also prove that La Rioja and Catalunya CCAA-generic pairs,
Murcia vehicle rows, and C Valenciana legal-window roles are not treated as
generated/pending siblings.

## Tests

`uv run ruff check src/aeat/domain/calculations/registry/_validate_semantic_roles.py src/aeat/domain/calculations/registry/test_semantic_role.py`

`uv run pytest src/aeat/domain/calculations/registry/test_semantic_role.py src/aeat/domain/calculations/registry/test_cross_revision_drift.py::test_singleton_semantic_role_warning_count_does_not_regress -q`
